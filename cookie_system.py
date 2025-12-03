import json
import asyncio
import logging
from urllib.parse import unquote
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import Playwright
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, TimeoutError
    PLAYWRIGHT_AVAILABLE = True
    logger.info("✅ Playwright is available")
except ImportError:
    logger.warning("❌ Playwright not installed. Run: pip install playwright")
    logger.warning("❌ Then run: playwright install chromium")
    PLAYWRIGHT_AVAILABLE = False

def log_console(message, user_id=None):
    """Log message to console"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    if user_id:
        logger.info(f"[{timestamp}] [{user_id}] {message}")
    else:
        logger.info(f"[{timestamp}] {message}")

def parse_cookies(cookie_input):
    """
    Parse cookies from various formats
    """
    cookies = []
    
    if not cookie_input or not cookie_input.strip():
        return cookies
    
    log_console(f"🔍 Parsing cookies input (length: {len(cookie_input)})")
    
    cookie_input = cookie_input.strip()
    
    # Method 1: Try JSON array format
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
                    log_console(f"✅ Parsed {len(cookies)} cookies from JSON array")
                    return cookies
        except json.JSONDecodeError:
            pass
    
    # Method 2: Try Netscape format or raw string
    cookie_input = cookie_input.replace('; ', ';').replace(' ;', ';')
    
    cookie_parts = []
    if ';' in cookie_input:
        cookie_parts = [part.strip() for part in cookie_input.split(';') if part.strip()]
    else:
        cookie_parts = [line.strip() for line in cookie_input.split('\n') if line.strip()]
    
    for part in cookie_parts:
        if not part or part.startswith('#') or part.startswith('//'):
            continue
        
        if part.lower().startswith(('#', '//', 'domain=', 'path=', 'expires=', 'secure', 'httponly')):
            continue
            
        if '=' in part:
            try:
                name_value = part.split('=', 1)
                if len(name_value) != 2:
                    continue
                    
                name, value = name_value
                name = name.strip()
                value = value.strip()
                
                name = name.replace('"', '').replace("'", "").replace(';', '')
                
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
                    elif 'instagram' in name.lower():
                        domain = '.instagram.com'
                    
                    cookies.append({
                        'name': name,
                        'value': value,
                        'domain': domain,
                        'path': '/',
                        'secure': True,
                        'httpOnly': name in ['xs', 'fr', 'c_user', 'sb']
                    })
                    log_console(f"✅ Added cookie: {name}={value[:20]}...")
                    
            except Exception as e:
                log_console(f"⚠️ Failed to parse cookie part: {part[:50]}... - Error: {e}")
                continue
    
    unique_cookies = []
    seen_names = set()
    for cookie in cookies:
        if cookie['name'] not in seen_names:
            unique_cookies.append(cookie)
            seen_names.add(cookie['name'])
    
    log_console(f"✅ Final parsed cookies: {len(unique_cookies)}")
    
    important_cookies = ['c_user', 'xs', 'fr', 'datr', 'sb']
    found_important = [c for c in unique_cookies if c['name'] in important_cookies]
    
    if found_important:
        log_console(f"🔑 Found important cookies: {[c['name'] for c in found_important]}")
    else:
        log_console("⚠️ No important session cookies found (c_user, xs, fr, etc.)")
    
    return unique_cookies[:30]

def get_facebook_account_info(cookies):
    """
    Extract Facebook account information from cookies
    """
    account_info = {
        'user_id': None,
        'user_name': 'Unknown',
        'is_valid': False,
        'has_xs': False,
        'has_c_user': False
    }
    
    try:
        for cookie in cookies:
            if cookie['name'] == 'c_user':
                account_info['user_id'] = cookie['value']
                account_info['has_c_user'] = True
            
            if cookie['name'] == 'xs':
                account_info['has_xs'] = True
        
        if account_info['user_id'] and account_info['has_xs']:
            account_info['is_valid'] = True
            account_info['user_name'] = f"User_{account_info['user_id'][:8]}"
            
        log_console(f"📊 Account Info: UserID: {account_info['user_id']}, Valid: {account_info['is_valid']}")
            
    except Exception as e:
        log_console(f"⚠️ Failed to extract account info: {e}")
    
    return account_info

async def simple_login_check(page, task_id, user_id):
    """Simple login check - DIRECT APPROACH"""
    try:
        log_console(f"[{task_id}] 🔐 Checking login with direct approach...", user_id)
        
        await page.goto('https://www.facebook.com/messages/t/', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        current_url = page.url
        
        logged_in = await page.evaluate("""
            () => {
                if (document.querySelector('[aria-label="Your profile"]') || 
                    document.querySelector('[data-testid="blue_bar_profile_link"]') ||
                    document.querySelector('[role="navigation"]') ||
                    document.querySelector('a[href*="/me/"]')) {
                    return true;
                }
                
                if (document.querySelector('[contenteditable="true"]') ||
                    document.querySelector('[aria-label*="Message" i]') ||
                    document.querySelector('[data-pagelet="ChatTab"]')) {
                    return true;
                }
                
                if (document.querySelector('div[role="banner"]') ||
                    document.querySelector('nav') ||
                    document.querySelector('[aria-label="Facebook"]')) {
                    return true;
                }
                
                return false;
            }
        """)
        
        if logged_in:
            log_console(f"[{task_id}] ✅ DIRECT LOGIN SUCCESSFUL!", user_id)
            
            profile_name = await extract_profile_name_from_page(page, task_id, user_id)
            return {'success': True, 'name': profile_name, 'id': 'Direct'}
        
        is_login_page = await page.evaluate("""
            () => {
                return document.querySelector('input[name="email"]') !== null ||
                       document.querySelector('input[type="password"]') !== null ||
                       document.querySelector('button[name="login"]') !== null ||
                       window.location.href.includes('login') ||
                       window.location.href.includes('checkpoint');
            }
        """)
        
        if is_login_page:
            log_console(f"[{task_id}] ❌ Login page detected - cookies may be invalid", user_id)
        
        return {'success': False, 'name': 'Login Failed', 'id': 'Unknown'}
        
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Direct login check failed: {e}", user_id)
        return {'success': False, 'name': 'Error', 'id': 'Unknown'}

async def extract_profile_name_from_page(page, task_id, user_id):
    """Extract actual Facebook profile name from page"""
    try:
        log_console(f"[{task_id}] 👤 Extracting profile name...", user_id)
        
        await page.wait_for_timeout(3000)
        
        profile_selectors = [
            '[aria-label="Your profile"]',
            '[data-testid="blue_bar_profile_link"]',
            'a[href*="/me/"]',
            'div[role="navigation"] [dir="auto"]',
            'span[dir="auto"]',
            'h1',
            'title'
        ]
        
        profile_name = "Facebook User"
        
        for selector in profile_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        text = await element.text_content()
                        if text:
                            text = text.strip()
                            if (len(text) > 1 and len(text) < 50 and
                                text.lower() not in ['facebook', 'home', 'friends', 'watch', 
                                                   'marketplace', 'groups', 'menu', 'messenger',
                                                   'notifications', 'search facebook'] and
                                not text.startswith('http') and
                                not text.isdigit()):
                                
                                profile_name = text
                                log_console(f"[{task_id}] ✅ Found profile name: {profile_name}", user_id)
                                return profile_name
                    except:
                        continue
            except:
                continue
        
        try:
            title = await page.title()
            if 'Facebook' in title:
                parts = title.split('|')
                if len(parts) > 0:
                    name_candidate = parts[0].strip()
                    if len(name_candidate) > 1 and name_candidate != 'Facebook':
                        profile_name = name_candidate
                        log_console(f"[{task_id}] ✅ Extracted name from title: {profile_name}", user_id)
                        return profile_name
        except:
            pass
        
        try:
            meta_name = await page.evaluate("""
                () => {
                    const meta = document.querySelector('meta[property="og:title"]') ||
                                 document.querySelector('meta[name="description"]');
                    return meta ? meta.getAttribute('content') : null;
                }
            """)
            
            if meta_name and 'Facebook' in meta_name:
                name_part = meta_name.split('-')[0].strip()
                if len(name_part) > 1:
                    profile_name = name_part
                    log_console(f"[{task_id}] ✅ Extracted name from meta: {profile_name}", user_id)
                    return profile_name
        except:
            pass
        
        return profile_name
        
    except Exception as e:
        log_console(f"[{task_id}] ⚠️ Profile name extraction failed: {e}", user_id)
        return "Facebook User"

async def find_and_send_message_improved(page, conversation_id, message, task_id, user_id):
    """Find conversation and send message - IMPROVED VERSION"""
    try:
        log_console(f"[{task_id}] 📨 Looking for conversation: {conversation_id}", user_id)
        
        direct_url = f'https://www.facebook.com/messages/t/{conversation_id}'
        await page.goto(direct_url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5000)
        
        current_url = page.url
        if conversation_id in current_url or 'messages/t/' in current_url:
            log_console(f"[{task_id}] ✅ Successfully navigated to conversation", user_id)
        else:
            log_console(f"[{task_id}] ⚠️ Not in conversation page, current URL: {current_url}", user_id)
        
        message_sent = False
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                input_selectors = [
                    '[contenteditable="true"]',
                    'div[aria-label="Message"]',
                    'div[role="textbox"]',
                    'textarea',
                    'input[type="text"]'
                ]
                
                message_input = None
                for selector in input_selectors:
                    try:
                        message_input = await page.wait_for_selector(selector, timeout=5000)
                        if message_input:
                            break
                    except:
                        continue
                
                if message_input:
                    await message_input.click()
                    await page.wait_for_timeout(1000)
                    
                    await message_input.evaluate('element => element.innerHTML = ""')
                    await page.wait_for_timeout(500)
                    
                    await message_input.type(message, delay=50)
                    await page.wait_for_timeout(1000)
                    
                    send_selectors = [
                        '[aria-label="Send"]',
                        'div[aria-label*="Send" i]',
                        'button:has-text("Send")',
                        'div[role="button"]:has-text("Send")'
                    ]
                    
                    send_button = None
                    for selector in send_selectors:
                        try:
                            send_button = await page.wait_for_selector(selector, timeout=3000)
                            if send_button:
                                break
                        except:
                            continue
                    
                    if send_button:
                        await send_button.click()
                        log_console(f"[{task_id}] ✅ Message sent successfully!", user_id)
                        message_sent = True
                        break
                    else:
                        await page.keyboard.press('Enter')
                        log_console(f"[{task_id}] ✅ Message sent with Enter key!", user_id)
                        message_sent = True
                        break
                else:
                    log_console(f"[{task_id}] ⚠️ Could not find message input (attempt {attempt + 1}/{max_attempts})", user_id)
                    await page.wait_for_timeout(2000)
                    
            except Exception as e:
                log_console(f"[{task_id}] ⚠️ Error sending message (attempt {attempt + 1}): {e}", user_id)
                await page.wait_for_timeout(2000)
        
        if message_sent:
            await page.wait_for_timeout(3000)
            return True
        else:
            log_console(f"[{task_id}] ❌ Failed to send message after {max_attempts} attempts", user_id)
            return False
            
    except Exception as e:
        log_console(f"[{task_id}] ❌ Error in message sending: {e}", user_id)
        return False

async def send_facebook_message_improved(cookies, conversation_id, message, task_id, user_id):
    """IMPROVED VERSION - With profile name and better message input"""
    if not PLAYWRIGHT_AVAILABLE:
        log_console(f"[{task_id}] ❌ Playwright not available", user_id)
        return False
    
    try:
        log_console(f"[{task_id}] 🚀 Starting browser session...", user_id)
        
        account_info = get_facebook_account_info(cookies)
        if account_info['is_valid']:
            log_console(f"[{task_id}] 👤 Cookie Account: {account_info['user_name']} (UID: {account_info['user_id']})", user_id)
        else:
            log_console(f"[{task_id}] ⚠️ Cookies may be invalid or expired", user_id)
            return False
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled',
                    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ],
                timeout=90000
            )
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            if cookies:
                try:
                    await context.add_cookies(cookies)
                    log_console(f"[{task_id}] ✅ Loaded {len(cookies)} cookies into browser", user_id)
                except Exception as e:
                    log_console(f"[{task_id}] ❌ Error adding cookies: {e}", user_id)
                    await browser.close()
                    return False
            
            page = await context.new_page()
            
            await page.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0'
            })
            
            # STEP 1: Login check
            login_result = await simple_login_check(page, task_id, user_id)
            
            if not login_result['success']:
                log_console(f"[{task_id}] ❌ LOGIN FAILED - Cookies may be invalid", user_id)
                
                try:
                    screenshot = await page.screenshot()
                    with open(f'debug_{task_id}_{datetime.now().strftime("%H%M%S")}.png', 'wb') as f:
                        f.write(screenshot)
                    log_console(f"[{task_id}] 📸 Debug screenshot saved", user_id)
                except:
                    pass
                
                await browser.close()
                return False
            
            log_console(f"[{task_id}] ✅ Logged in as: {login_result['name']}", user_id)
            
            # STEP 2: Send message
            success = await find_and_send_message_improved(page, conversation_id, message, task_id, user_id)
            
            if success:
                try:
                    screenshot = await page.screenshot()
                    with open(f'success_{task_id}_{datetime.now().strftime("%H%M%S")}.png', 'wb') as f:
                        f.write(screenshot)
                except:
                    pass
            
            await browser.close()
            return success
            
    except Exception as e:
        log_console(f"[{task_id}] ❌ Browser session error: {str(e)}", user_id)
        return False

def check_cookie_validity(cookies):
    """
    Quick check if cookies appear to be valid Facebook cookies
    """
    if not cookies:
        return False
    
    account_info = get_facebook_account_info(cookies)
    return account_info['is_valid']
