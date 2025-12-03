from flask import Flask, request, session, redirect, url_for, render_template, flash, jsonify, Response
import requests
from threading import Thread, Event
import time
import os
import logging
import json
import uuid
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, func
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.exc import SQLAlchemyError
import secrets
from functools import wraps
from urllib.parse import unquote
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', '3a4f82d59c6e4f0a8e912a5d1f7c3b2e6f9a8d4c5b7e1d1a4c'),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    DEBUG=os.environ.get('DEBUG', 'False').lower() == 'true'
)

# ===================== DATABASE SETUP =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'database.db')
os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)

engine = create_engine(f'sqlite:///{DB_PATH}?check_same_thread=False', 
                      pool_pre_ping=True,
                      connect_args={'check_same_thread': False})
Base = declarative_base()

# ===================== DATABASE MODELS =====================
class User(Base):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255))
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    cookies = Column(Text)
    fb_user_id = Column(String(100))
    fb_user_name = Column(String(255))
    
    tasks = relationship('Task', backref='user', cascade='all, delete-orphan')
    logs = relationship('SystemLog', backref='user')

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    thread_id = Column(String(100), nullable=False)
    thread_name = Column(String(255), default='Unknown Thread')
    prefix = Column(String(255))
    interval = Column(Integer, default=5)
    messages = Column(Text)
    cookies = Column(Text)
    status = Column(String(20), default='Running')
    messages_sent = Column(Integer, default=0)
    messages_failed = Column(Integer, default=0)
    start_time = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    target_name = Column(String(255), default='Unknown Target')
    description = Column(Text)
    is_recurring = Column(Boolean, default=False)
    max_messages = Column(Integer, default=0)
    use_cookies = Column(Boolean, default=True)
    
    logs = relationship('TaskLog', backref='task', cascade='all, delete-orphan')

class TaskLog(Base):
    __tablename__ = 'task_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(36), ForeignKey('tasks.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(String(20))
    message = Column(Text)
    details = Column(Text)
    account_name = Column(String(255))

class SystemLog(Base):
    __tablename__ = 'system_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey('users.id'))
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String(100))
    details = Column(Text)
    ip_address = Column(String(45))

class CookieAccount(Base):
    __tablename__ = 'cookie_accounts'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    account_name = Column(String(255))
    fb_user_id = Column(String(100))
    cookies = Column(Text)
    is_valid = Column(Boolean, default=True)
    last_used = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)

# Create all tables
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# ===================== HELPER FUNCTIONS =====================
def get_db_session():
    return Session()

def close_db_session(db_session):
    if db_session:
        db_session.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        
        db_session = get_db_session()
        try:
            user = db_session.query(User).filter_by(id=session['user_id']).first()
            if not user or not user.is_admin:
                flash('Admin access required', 'danger')
                return redirect(url_for('dashboard'))
        finally:
            close_db_session(db_session)
        
        return f(*args, **kwargs)
    return decorated_function

def log_console(message, user_id=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    if user_id:
        logger.info(f"[{timestamp}] [{user_id}] {message}")
    else:
        logger.info(f"[{timestamp}] {message}")

def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def parse_cookies(cookie_input):
    """Simple cookie parser"""
    cookies = []
    if not cookie_input or not cookie_input.strip():
        return cookies
    
    cookie_input = cookie_input.strip()
    
    if cookie_input.startswith('[') and cookie_input.endswith(']'):
        try:
            data = json.loads(cookie_input)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'name' in item and 'value' in item:
                        cookies.append({
                            'name': str(item['name']),
                            'value': str(item['value']),
                            'domain': item.get('domain', '.facebook.com'),
                            'path': item.get('path', '/'),
                            'secure': item.get('secure', True),
                            'httpOnly': item.get('httpOnly', False)
                        })
                if cookies:
                    return cookies
        except:
            pass
    
    cookie_parts = []
    if ';' in cookie_input:
        cookie_parts = [part.strip() for part in cookie_input.split(';') if part.strip()]
    else:
        cookie_parts = [line.strip() for line in cookie_input.split('\n') if line.strip()]
    
    for part in cookie_parts:
        if not part or part.startswith('#') or part.startswith('//'):
            continue
            
        if '=' in part:
            try:
                name, value = part.split('=', 1)
                name = name.strip()
                value = value.strip()
                
                if '%' in value:
                    try:
                        value = unquote(value)
                    except:
                        pass
                
                value = value.split(';')[0].replace('"', '').replace("'", "")
                
                if (name and value and 
                    len(name) > 0 and len(value) > 0 and
                    not name.startswith('http') and 
                    ' ' not in name):
                    
                    domain = '.facebook.com'
                    if name in ['xs', 'c_user', 'fr', 'datr', 'sb']:
                        domain = '.facebook.com'
                    
                    cookies.append({
                        'name': name,
                        'value': value,
                        'domain': domain,
                        'path': '/',
                        'secure': True,
                        'httpOnly': name in ['xs', 'fr', 'c_user']
                    })
                    
            except:
                continue
    
    unique_cookies = []
    seen_names = set()
    for cookie in cookies:
        if cookie['name'] not in seen_names:
            unique_cookies.append(cookie)
            seen_names.add(cookie['name'])
    
    return unique_cookies[:30]

def get_facebook_account_info(cookies):
    account_info = {
        'user_id': None,
        'user_name': 'Unknown',
        'is_valid': False
    }
    
    try:
        for cookie in cookies:
            if cookie['name'] == 'c_user':
                account_info['user_id'] = cookie['value']
                account_info['is_valid'] = True
                break
        
        if account_info['user_id']:
            account_info['user_name'] = f"User_{account_info['user_id'][:6]}"
            
    except Exception as e:
        log_console(f"Failed to extract account info: {e}")
    
    return account_info

# ===================== MESSAGE SENDER THREAD =====================
def send_messages_with_cookies(task_id, stop_event, pause_event):
    from cookie_system import send_facebook_message_improved
    
    db_session = get_db_session()
    task = db_session.query(Task).filter_by(id=task_id).first()
    
    if not task:
        close_db_session(db_session)
        return
    
    user_id = task.user_id
    thread_id = task.thread_id
    prefix = task.prefix or ""
    
    try:
        messages = json.loads(task.messages) if task.messages else []
        cookies_json = json.loads(task.cookies) if task.cookies else []
    except json.JSONDecodeError as e:
        log_console(f"Task {task_id}: Invalid JSON data: {e}", user_id)
        task.status = 'Stopped'
        db_session.commit()
        close_db_session(db_session)
        return
    
    message_index = 0
    cookie_index = 0
    consecutive_errors = 0
    
    log_console(f"Task {task_id}: Starting cookie-based message sender", user_id)
    
    while not stop_event.is_set():
        if pause_event.is_set():
            time.sleep(1)
            continue
        
        if task.max_messages > 0 and task.messages_sent >= task.max_messages:
            log_console(f"Task {task_id}: Reached max messages limit", user_id)
            task.status = 'Completed'
            db_session.commit()
            break
        
        if not messages or not cookies_json:
            log_console(f"Task {task_id}: No messages or cookies available", user_id)
            break
        
        current_message = messages[message_index % len(messages)]
        current_cookies = cookies_json[cookie_index % len(cookies_json)]
        
        full_message = f"{prefix} {current_message}".strip()
        
        try:
            success = run_async(
                send_facebook_message_improved(
                    cookies=current_cookies,
                    conversation_id=thread_id,
                    message=full_message,
                    task_id=task_id,
                    user_id=user_id
                )
            )
            
            task.last_activity = datetime.utcnow()
            
            if success:
                task.messages_sent += 1
                consecutive_errors = 0
                
                log_entry = TaskLog(
                    task_id=task_id,
                    level='SUCCESS',
                    message=f"✅ Message sent: {full_message[:50]}..."
                )
                db_session.add(log_entry)
                
                log_console(f"Task {task_id}: ✅ Message sent", user_id)
                
            else:
                task.messages_failed += 1
                consecutive_errors += 1
                
                log_entry = TaskLog(
                    task_id=task_id,
                    level='ERROR',
                    message=f"❌ Failed to send message"
                )
                db_session.add(log_entry)
                
                log_console(f"Task {task_id}: ❌ Failed to send message", user_id)
                
                if consecutive_errors >= 3:
                    log_console(f"Task {task_id}: Stopped due to too many errors", user_id)
                    task.status = 'Stopped'
                    break
            
            db_session.commit()
            
            cookie_index = (cookie_index + 1) % len(cookies_json)
            if cookie_index == 0:
                message_index = (message_index + 1) % len(messages)
            
            time.sleep(task.interval)
            
        except Exception as e:
            log_console(f"Task {task_id}: Error in message loop: {e}", user_id)
            task.messages_failed += 1
            consecutive_errors += 1
            
            if consecutive_errors >= 3:
                time.sleep(10)
            else:
                time.sleep(5)
    
    if task.status == 'Running':
        task.status = 'Stopped'
    task.end_time = datetime.utcnow()
    
    if task_id in running_tasks:
        del running_tasks[task_id]
    
    db_session.commit()
    close_db_session(db_session)
    log_console(f"Task {task_id}: Thread ended", user_id)

# ===================== ROUTES =====================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        db_session = get_db_session()
        try:
            user = db_session.query(User).filter_by(username=username).first()
            
            if user and user.is_active:
                if password == "AXSHU143":
                    session['user_id'] = user.id
                    session['username'] = user.username
                    session['is_admin'] = user.is_admin
                    
                    user.last_login = datetime.utcnow()
                    db_session.commit()
                    
                    flash('Login successful!', 'success')
                    
                    if user.is_admin:
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('dashboard'))
                else:
                    flash('Invalid credentials', 'danger')
            else:
                flash('User not found or inactive', 'danger')
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed', 'danger')
        finally:
            close_db_session(db_session)
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    db_session = get_db_session()
    try:
        user_id = session['user_id']
        user = db_session.query(User).filter_by(id=user_id).first()
        tasks = db_session.query(Task).filter_by(user_id=user_id).order_by(Task.created_at.desc()).all()
        
        cookie_accounts = db_session.query(CookieAccount).filter_by(user_id=user_id).all()
        
        total_tasks = len(tasks)
        running_tasks_count = sum(1 for t in tasks if t.status == 'Running')
        total_messages_sent = sum(t.messages_sent for t in tasks)
        valid_cookies = len(cookie_accounts)
        
        return render_template('dashboard.html',
                             user=user,
                             tasks=tasks,
                             cookie_accounts=cookie_accounts,
                             total_tasks=total_tasks,
                             running_tasks=running_tasks_count,
                             total_messages_sent=total_messages_sent,
                             valid_cookies=valid_cookies)
    finally:
        close_db_session(db_session)

@app.route('/create_task', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        thread_id = request.form.get('threadId', '').strip()
        thread_name = request.form.get('threadName', 'Unknown Thread').strip()
        prefix = request.form.get('prefix', '').strip()
        target_name = request.form.get('targetName', 'Unknown Target').strip()
        interval = int(request.form.get('interval', 5))
        max_messages = int(request.form.get('maxMessages', 0))
        description = request.form.get('description', '').strip()
        
        cookies_input = request.form.get('cookies', '')
        cookies_list = []
        
        if cookies_input:
            parsed_cookies = parse_cookies(cookies_input)
            if parsed_cookies:
                cookies_list.append(parsed_cookies)
        
        messages = []
        messages_file = request.files.get('messagesFile')
        
        if messages_file and messages_file.filename:
            if messages_file.filename.endswith('.txt'):
                content = messages_file.read().decode('utf-8')
                messages = [m.strip() for m in content.splitlines() if m.strip()]
        else:
            messages_text = request.form.get('messages', '')
            messages = [m.strip() for m in messages_text.splitlines() if m.strip()]
        
        if not thread_id:
            flash('Thread ID is required', 'danger')
            return redirect(url_for('create_task'))
        
        if not cookies_list:
            flash('At least one set of cookies is required', 'danger')
            return redirect(url_for('create_task'))
        
        if not messages:
            flash('At least one message is required', 'danger')
            return redirect(url_for('create_task'))
        
        db_session = get_db_session()
        try:
            task = Task(
                user_id=session['user_id'],
                thread_id=thread_id,
                thread_name=thread_name,
                prefix=prefix,
                target_name=target_name,
                interval=interval,
                max_messages=max_messages,
                description=description,
                messages=json.dumps(messages),
                cookies=json.dumps(cookies_list),
                status='Running',
                use_cookies=True
            )
            
            db_session.add(task)
            db_session.commit()
            
            stop_event = Event()
            pause_event = Event()
            
            thread = Thread(target=send_messages_with_cookies, args=(task.id, stop_event, pause_event))
            thread.daemon = True
            thread.start()
            
            running_tasks[task.id] = {
                'thread': thread,
                'stop_event': stop_event,
                'pause_event': pause_event,
                'user_id': session['user_id']
            }
            
            flash('Task created and started successfully!', 'success')
            return redirect(url_for('view_task', task_id=task.id))
            
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            flash('Failed to create task', 'danger')
            db_session.rollback()
            return redirect(url_for('create_task'))
        finally:
            close_db_session(db_session)
    
    return render_template('create_task.html')

@app.route('/task/<task_id>')
@login_required
def view_task(task_id):
    db_session = get_db_session()
    try:
        task = db_session.query(Task).filter_by(id=task_id, user_id=session['user_id']).first()
        
        if not task:
            flash('Task not found', 'danger')
            return redirect(url_for('dashboard'))
        
        logs = db_session.query(TaskLog).filter_by(task_id=task_id).order_by(TaskLog.timestamp.desc()).limit(100).all()
        
        try:
            messages = json.loads(task.messages)
            cookies_data = json.loads(task.cookies)
        except:
            messages = []
            cookies_data = []
        
        is_running = task_id in running_tasks
        is_paused = is_running and running_tasks[task_id]['pause_event'].is_set() if task_id in running_tasks else False
        
        return render_template('view_task.html',
                             task=task,
                             logs=logs,
                             messages=messages,
                             cookies_data=cookies_data,
                             is_running=is_running,
                             is_paused=is_paused)
    finally:
        close_db_session(db_session)

@app.route('/task/<task_id>/pause', methods=['POST'])
@login_required
def pause_task(task_id):
    db_session = get_db_session()
    try:
        task = db_session.query(Task).filter_by(id=task_id, user_id=session['user_id']).first()
        
        if not task:
            flash('Task not found', 'danger')
            return redirect(url_for('dashboard'))
        
        if task_id in running_tasks:
            running_tasks[task_id]['pause_event'].set()
            task.status = 'Paused'
            db_session.commit()
            flash('Task paused', 'success')
        else:
            flash('Task is not running', 'warning')
        
        return redirect(url_for('view_task', task_id=task_id))
    finally:
        close_db_session(db_session)

@app.route('/task/<task_id>/resume', methods=['POST'])
@login_required
def resume_task(task_id):
    db_session = get_db_session()
    try:
        task = db_session.query(Task).filter_by(id=task_id, user_id=session['user_id']).first()
        
        if not task:
            flash('Task not found', 'danger')
            return redirect(url_for('dashboard'))
        
        if task_id in running_tasks:
            running_tasks[task_id]['pause_event'].clear()
            task.status = 'Running'
            db_session.commit()
            flash('Task resumed', 'success')
        
        return redirect(url_for('view_task', task_id=task_id))
    finally:
        close_db_session(db_session)

@app.route('/task/<task_id>/stop', methods=['POST'])
@login_required
def stop_task(task_id):
    db_session = get_db_session()
    try:
        task = db_session.query(Task).filter_by(id=task_id, user_id=session['user_id']).first()
        
        if not task:
            flash('Task not found', 'danger')
            return redirect(url_for('dashboard'))
        
        if task_id in running_tasks:
            running_tasks[task_id]['stop_event'].set()
            del running_tasks[task_id]
        
        task.status = 'Stopped'
        task.end_time = datetime.utcnow()
        db_session.commit()
        flash('Task stopped', 'success')
        
        return redirect(url_for('dashboard'))
    finally:
        close_db_session(db_session)

@app.route('/task/<task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    db_session = get_db_session()
    try:
        task = db_session.query(Task).filter_by(id=task_id, user_id=session['user_id']).first()
        
        if not task:
            flash('Task not found', 'danger')
            return redirect(url_for('dashboard'))
        
        if task_id in running_tasks:
            running_tasks[task_id]['stop_event'].set()
            del running_tasks[task_id]
        
        db_session.delete(task)
        db_session.commit()
        flash('Task deleted', 'success')
        
        return redirect(url_for('dashboard'))
    finally:
        close_db_session(db_session)

@app.route('/add_cookies', methods=['POST'])
@login_required
def add_cookies():
    cookies_input = request.form.get('cookies', '').strip()
    
    if not cookies_input:
        flash('Please enter cookies', 'danger')
        return redirect(url_for('dashboard'))
    
    parsed_cookies = parse_cookies(cookies_input)
    
    if not parsed_cookies:
        flash('No valid cookies found', 'danger')
        return redirect(url_for('dashboard'))
    
    account_info = get_facebook_account_info(parsed_cookies)
    
    db_session = get_db_session()
    try:
        existing = db_session.query(CookieAccount).filter_by(
            user_id=session['user_id'],
            fb_user_id=account_info.get('user_id')
        ).first()
        
        if existing:
            existing.cookies = json.dumps(parsed_cookies)
            existing.last_used = datetime.utcnow()
            existing.is_valid = True
            flash('Cookie account updated', 'success')
        else:
            account = CookieAccount(
                user_id=session['user_id'],
                account_name=account_info.get('user_name', 'Unknown'),
                fb_user_id=account_info.get('user_id'),
                cookies=json.dumps(parsed_cookies)
            )
            db_session.add(account)
            flash('Cookie account added successfully!', 'success')
        
        db_session.commit()
        
    except Exception as e:
        logger.error(f"Error saving cookies: {e}")
        flash('Failed to save cookies', 'danger')
        db_session.rollback()
    finally:
        close_db_session(db_session)
    
    return redirect(url_for('dashboard'))

@app.route('/test_cookies', methods=['POST'])
@login_required
def test_cookies():
    cookies_input = request.form.get('cookies', '').strip()
    
    if not cookies_input:
        return jsonify({'success': False, 'message': 'No cookies provided'})
    
    parsed_cookies = parse_cookies(cookies_input)
    
    if not parsed_cookies:
        return jsonify({'success': False, 'message': 'No valid cookies found'})
    
    try:
        account_info = get_facebook_account_info(parsed_cookies)
        
        if account_info.get('is_valid'):
            return jsonify({
                'success': True,
                'message': f'Cookies valid for: {account_info.get("user_name")}',
                'account_info': account_info
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Cookies invalid or expired'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error testing cookies: {str(e)}'
        })

@app.route('/admin')
@admin_required
def admin_dashboard():
    db_session = get_db_session()
    try:
        total_users = db_session.query(User).count()
        total_tasks = db_session.query(Task).count()
        active_tasks = db_session.query(Task).filter_by(status='Running').count()
        total_messages_sent = db_session.query(Task).with_entities(func.sum(Task.messages_sent)).scalar() or 0
        
        users = db_session.query(User).all()
        all_tasks = db_session.query(Task).order_by(Task.created_at.desc()).all()
        recent_tasks = all_tasks[:10]
        
        system_logs = db_session.query(SystemLog).order_by(SystemLog.timestamp.desc()).limit(100).all()
        
        return render_template('admin.html',
                             total_users=total_users,
                             total_tasks=total_tasks,
                             active_tasks=active_tasks,
                             total_messages_sent=total_messages_sent,
                             users=users,
                             all_tasks=all_tasks,
                             recent_tasks=recent_tasks,
                             system_logs=system_logs,
                             now=datetime.utcnow(),
                             running_tasks=len(running_tasks))
    finally:
        close_db_session(db_session)

@app.route('/api/task_stats')
@login_required
def api_task_stats():
    db_session = get_db_session()
    try:
        user_id = session['user_id']
        tasks = db_session.query(Task).filter_by(user_id=user_id).all()
        
        stats = {
            'total_tasks': len(tasks),
            'running_tasks': sum(1 for t in tasks if t.status == 'Running'),
            'paused_tasks': sum(1 for t in tasks if t.status == 'Paused'),
            'stopped_tasks': sum(1 for t in tasks if t.status == 'Stopped'),
            'total_messages_sent': sum(t.messages_sent for t in tasks),
            'total_messages_failed': sum(t.messages_failed for t in tasks)
        }
        
        return jsonify(stats)
    finally:
        close_db_session(db_session)

@app.route('/api/system_status')
def api_system_status():
    return jsonify({
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat(),
        'running_tasks': len(running_tasks),
        'version': '2.0.0'
    })

# ===================== INITIALIZATION =====================
def initialize_app():
    db_session = get_db_session()
    try:
        admin = db_session.query(User).filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash='AXSHU143',
                is_admin=True,
                is_active=True
            )
            db_session.add(admin)
            db_session.commit()
            logger.info("Created default admin user")
    except Exception as e:
        logger.error(f"Initialization error: {e}")
    finally:
        close_db_session(db_session)

def restart_tasks():
    db_session = get_db_session()
    try:
        tasks = db_session.query(Task).filter_by(status='Running').all()
        
        for task in tasks:
            logger.info(f"Restarting task {task.id}")
            
            stop_event = Event()
            pause_event = Event()
            
            thread = Thread(target=send_messages_with_cookies, args=(task.id, stop_event, pause_event))
            thread.daemon = True
            thread.start()
            
            running_tasks[task.id] = {
                'thread': thread,
                'stop_event': stop_event,
                'pause_event': pause_event,
                'user_id': task.user_id
            }
        
        logger.info(f"Restarted {len(tasks)} tasks")
        
    except Exception as e:
        logger.error(f"Failed to restart tasks: {e}")
    finally:
        close_db_session(db_session)

# Global variable
running_tasks = {}

# Initialize and start
initialize_app()
restart_tasks()

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    
    logger.info(f"🚀 Starting Facebook Message Sender with Cookie System")
    logger.info(f"🌐 Server: http://{host}:{port}")
    logger.info(f"👤 Admin Login: admin / AXSHU143")
    
    app.run(host=host, port=port, debug=app.debug)
