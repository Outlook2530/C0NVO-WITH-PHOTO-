// ===================== GLOBAL VARIABLES =====================
const API_BASE_URL = window.location.origin;

// ===================== UTILITY FUNCTIONS =====================
class Utils {
    static showToast(message, type = 'info', duration = 3000) {
        // Remove existing toasts
        const existingToasts = document.querySelectorAll('.custom-toast');
        existingToasts.forEach(toast => toast.remove());
        
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                gap: 10px;
            `;
            document.body.appendChild(toastContainer);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `custom-toast alert alert-${type}`;
        toast.style.cssText = `
            min-width: 300px;
            max-width: 400px;
            padding: 12px 16px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease-out;
        `;
        
        // Add icon based on type
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        else if (type === 'danger') icon = '❌';
        else if (type === 'warning') icon = '⚠️';
        
        toast.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 10px;">
                <span style="font-size: 18px;">${icon}</span>
                <div style="flex: 1;">
                    <strong style="display: block; margin-bottom: 4px;">${this.capitalize(type)}</strong>
                    <div>${message}</div>
                </div>
                <button type="button" class="close-toast" style="background: none; border: none; font-size: 18px; cursor: pointer; color: #666;">&times;</button>
            </div>
        `;
        
        // Add close functionality
        const closeBtn = toast.querySelector('.close-toast');
        closeBtn.onclick = () => toast.remove();
        
        // Add to container
        toastContainer.appendChild(toast);
        
        // Auto remove after duration
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
        
        // Add CSS for animation
        this.addToastStyles();
    }
    
    static capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
    
    static addToastStyles() {
        if (!document.getElementById('toast-styles')) {
            const style = document.createElement('style');
            style.id = 'toast-styles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    static formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    static formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    static copyToClipboard(text) {
        navigator.clipboard.writeText(text)
            .then(() => this.showToast('Copied to clipboard!', 'success'))
            .catch(err => this.showToast('Failed to copy: ' + err, 'danger'));
    }
    
    static validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    static validateURL(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    }
}

// ===================== API FUNCTIONS =====================
class API {
    static async get(endpoint) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('GET Error:', error);
            Utils.showToast(`Failed to fetch data: ${error.message}`, 'danger');
            throw error;
        }
    }
    
    static async post(endpoint, data) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('POST Error:', error);
            Utils.showToast(`Failed to save: ${error.message}`, 'danger');
            throw error;
        }
    }
    
    static async postForm(endpoint, formData) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Form POST Error:', error);
            Utils.showToast(`Failed to submit form: ${error.message}`, 'danger');
            throw error;
        }
    }
}

// ===================== TASK MANAGEMENT =====================
class TaskManager {
    constructor() {
        this.tasks = [];
        this.init();
    }
    
    init() {
        // Initialize task management
        this.bindEvents();
        this.loadTasks();
    }
    
    bindEvents() {
        // Task creation form
        const taskForm = document.getElementById('task-form');
        if (taskForm) {
            taskForm.addEventListener('submit', (e) => this.handleCreateTask(e));
        }
        
        // Task actions
        document.addEventListener('click', (e) => {
            if (e.target.closest('.pause-task')) {
                e.preventDefault();
                const taskId = e.target.closest('.pause-task').dataset.taskId;
                this.pauseTask(taskId);
            }
            
            if (e.target.closest('.resume-task')) {
                e.preventDefault();
                const taskId = e.target.closest('.resume-task').dataset.taskId;
                this.resumeTask(taskId);
            }
            
            if (e.target.closest('.stop-task')) {
                e.preventDefault();
                const taskId = e.target.closest('.stop-task').dataset.taskId;
                this.stopTask(taskId);
            }
            
            if (e.target.closest('.delete-task')) {
                e.preventDefault();
                const taskId = e.target.closest('.delete-task').dataset.taskId;
                this.deleteTask(taskId);
            }
        });
    }
    
    async loadTasks() {
        try {
            const data = await API.get('/api/task_stats');
            this.tasks = data.tasks || [];
            this.updateTaskList();
        } catch (error) {
            console.error('Failed to load tasks:', error);
        }
    }
    
    async handleCreateTask(e) {
        e.preventDefault();
        
        const form = e.target;
        const formData = new FormData(form);
        
        try {
            const result = await API.postForm('/create_task', formData);
            
            if (result.success) {
                Utils.showToast('Task created successfully!', 'success');
                form.reset();
                this.loadTasks();
                
                // Redirect to task page if task_id is provided
                if (result.task_id) {
                    setTimeout(() => {
                        window.location.href = `/task/${result.task_id}`;
                    }, 1500);
                }
            }
        } catch (error) {
            console.error('Failed to create task:', error);
        }
    }
    
    async pauseTask(taskId) {
        if (!confirm('Are you sure you want to pause this task?')) return;
        
        try {
            await API.post(`/task/${taskId}/pause`);
            Utils.showToast('Task paused', 'warning');
            this.loadTasks();
        } catch (error) {
            console.error('Failed to pause task:', error);
        }
    }
    
    async resumeTask(taskId) {
        try {
            await API.post(`/task/${taskId}/resume`);
            Utils.showToast('Task resumed', 'success');
            this.loadTasks();
        } catch (error) {
            console.error('Failed to resume task:', error);
        }
    }
    
    async stopTask(taskId) {
        if (!confirm('Are you sure you want to stop this task?')) return;
        
        try {
            await API.post(`/task/${taskId}/stop`);
            Utils.showToast('Task stopped', 'danger');
            this.loadTasks();
        } catch (error) {
            console.error('Failed to stop task:', error);
        }
    }
    
    async deleteTask(taskId) {
        if (!confirm('Are you sure you want to delete this task? This action cannot be undone.')) return;
        
        try {
            await API.post(`/task/${taskId}/delete`);
            Utils.showToast('Task deleted', 'danger');
            this.loadTasks();
        } catch (error) {
            console.error('Failed to delete task:', error);
        }
    }
    
    updateTaskList() {
        const taskList = document.getElementById('task-list');
        if (!taskList) return;
        
        if (this.tasks.length === 0) {
            taskList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-tasks fa-3x"></i>
                    <h4>No tasks yet</h4>
                    <p>Create your first task to get started</p>
                    <a href="/create_task" class="btn btn-primary">Create Task</a>
                </div>
            `;
            return;
        }
        
        taskList.innerHTML = this.tasks.map(task => `
            <div class="task-item ${task.status.toLowerCase()}" data-task-id="${task.id}">
                <div class="task-info">
                    <div class="task-header">
                        <h5>${task.thread_name}</h5>
                        <span class="task-status ${task.status.toLowerCase()}">${task.status}</span>
                    </div>
                    <div class="task-details">
                        <span><i class="fas fa-hashtag"></i> ${task.id.substring(0, 8)}...</span>
                        <span><i class="fas fa-paper-plane"></i> ${task.messages_sent} sent</span>
                        <span><i class="fas fa-clock"></i> ${Utils.formatDate(task.start_time)}</span>
                    </div>
                </div>
                <div class="task-actions">
                    <a href="/task/${task.id}" class="btn btn-sm btn-outline">
                        <i class="fas fa-eye"></i>
                    </a>
                    ${task.status === 'Running' ? `
                        <button class="btn btn-sm btn-warning pause-task" data-task-id="${task.id}">
                            <i class="fas fa-pause"></i>
                        </button>
                    ` : ''}
                    ${task.status === 'Paused' ? `
                        <button class="btn btn-sm btn-success resume-task" data-task-id="${task.id}">
                            <i class="fas fa-play"></i>
                        </button>
                    ` : ''}
                    <button class="btn btn-sm btn-danger stop-task" data-task-id="${task.id}">
                        <i class="fas fa-stop"></i>
                    </button>
                </div>
            </div>
        `).join('');
    }
}

// ===================== COOKIE MANAGEMENT =====================
class CookieManager {
    constructor() {
        this.init();
    }
    
    init() {
        this.bindEvents();
    }
    
    bindEvents() {
        // Cookie testing
        const testBtn = document.getElementById('test-cookies-btn');
        if (testBtn) {
            testBtn.addEventListener('click', () => this.testCookies());
        }
        
        // Cookie saving
        const saveBtn = document.getElementById('save-cookies-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveCookies());
        }
        
        // Cookie parsing examples
        const exampleBtn = document.getElementById('show-example-btn');
        if (exampleBtn) {
            exampleBtn.addEventListener('click', () => this.showExample());
        }
    }
    
    async testCookies() {
        const cookieInput = document.getElementById('cookie-input');
        if (!cookieInput || !cookieInput.value.trim()) {
            Utils.showToast('Please enter cookies to test', 'warning');
            return;
        }
        
        const testBtn = document.getElementById('test-cookies-btn');
        const originalText = testBtn.innerHTML;
        testBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        testBtn.disabled = true;
        
        try {
            const response = await fetch('/test_cookies', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `cookies=${encodeURIComponent(cookieInput.value)}`
            });
            
            const result = await response.json();
            
            if (result.success) {
                Utils.showToast(`✅ Cookies valid for: ${result.account_info.user_name}`, 'success');
                
                // Update result display
                const resultDiv = document.getElementById('test-result');
                if (resultDiv) {
                    resultDiv.innerHTML = `
                        <div class="alert alert-success">
                            <h6><i class="fas fa-check-circle"></i> Cookies Valid!</h6>
                            <p>Account: ${result.account_info.user_name}</p>
                            <p>User ID: ${result.account_info.user_id}</p>
                            <small class="text-muted">Cookies are ready to use</small>
                        </div>
                    `;
                }
            } else {
                Utils.showToast(`❌ ${result.message}`, 'danger');
                
                const resultDiv = document.getElementById('test-result');
                if (resultDiv) {
                    resultDiv.innerHTML = `
                        <div class="alert alert-danger">
                            <h6><i class="fas fa-times-circle"></i> Cookies Invalid</h6>
                            <p>${result.message}</p>
                            <small class="text-muted">Please check your cookies and try again</small>
                        </div>
                    `;
                }
            }
        } catch (error) {
            Utils.showToast('Failed to test cookies: ' + error.message, 'danger');
        } finally {
            testBtn.innerHTML = originalText;
            testBtn.disabled = false;
        }
    }
    
    async saveCookies() {
        const cookieInput = document.getElementById('cookie-input');
        if (!cookieInput || !cookieInput.value.trim()) {
            Utils.showToast('Please enter cookies to save', 'warning');
            return;
        }
        
        if (!confirm('Save these cookies to your account?')) return;
        
        const saveBtn = document.getElementById('save-cookies-btn');
        const originalText = saveBtn.innerHTML;
        saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
        saveBtn.disabled = true;
        
        try {
            const response = await fetch('/add_cookies', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `cookies=${encodeURIComponent(cookieInput.value)}`
            });
            
            if (response.ok) {
                Utils.showToast('✅ Cookies saved successfully!', 'success');
                
                // Clear input
                cookieInput.value = '';
                
                // Close modal if exists
                const modal = bootstrap.Modal.getInstance(document.getElementById('cookieModal'));
                if (modal) modal.hide();
                
                // Refresh page after delay
                setTimeout(() => location.reload(), 1500);
            } else {
                throw new Error('Failed to save cookies');
            }
        } catch (error) {
            Utils.showToast('Failed to save cookies: ' + error.message, 'danger');
        } finally {
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = false;
        }
    }
    
    showExample() {
        const example = `c_user=100123456789;
xs=45:AbCdEfGhIjKlMnOp:9876543210;
fr=1AbCdEfGhIjKlMnOp.9876543210.9876543210;
datr=AbCdEfGhIjKlMnOp;
sb=AbCdEfGhIjKlMnOp`;

        const cookieInput = document.getElementById('cookie-input');
        if (cookieInput) {
            cookieInput.value = example;
            Utils.showToast('Example cookies loaded', 'info');
        }
    }
}

// ===================== DASHBOARD STATS =====================
class DashboardStats {
    constructor() {
        this.stats = {};
        this.init();
    }
    
    init() {
        this.loadStats();
        this.bindEvents();
    }
    
    bindEvents() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-stats-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadStats());
        }
        
        // Auto-refresh every 30 seconds
        setInterval(() => this.loadStats(), 30000);
    }
    
    async loadStats() {
        try {
            const data = await API.get('/api/task_stats');
            this.stats = data;
            this.updateDisplay();
        } catch (error) {
            console.error('Failed to load stats:', error);
        }
    }
    
    updateDisplay() {
        // Update total tasks
        const totalTasksEl = document.getElementById('total-tasks');
        if (totalTasksEl) {
            totalTasksEl.textContent = this.stats.total_tasks || 0;
        }
        
        // Update running tasks
        const runningTasksEl = document.getElementById('running-tasks');
        if (runningTasksEl) {
            runningTasksEl.textContent = this.stats.running_tasks || 0;
        }
        
        // Update messages sent
        const messagesSentEl = document.getElementById('messages-sent');
        if (messagesSentEl) {
            messagesSentEl.textContent = Utils.formatNumber(this.stats.total_messages_sent || 0);
        }
        
        // Update success rate
        const successRateEl = document.getElementById('success-rate');
        if (successRateEl && this.stats.total_messages_sent && this.stats.total_messages_failed) {
            const total = this.stats.total_messages_sent + this.stats.total_messages_failed;
            const rate = total > 0 ? (this.stats.total_messages_sent / total * 100).toFixed(1) : 0;
            successRateEl.textContent = `${rate}%`;
        }
        
        // Update last update time
        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = new Date().toLocaleTimeString();
        }
    }
}

// ===================== REAL-TIME UPDATES =====================
class RealTimeUpdates {
    constructor() {
        this.eventSource = null;
        this.init();
    }
    
    init() {
        if (window.location.pathname.includes('/task/')) {
            this.connectToUpdates();
        }
    }
    
    connectToUpdates() {
        const taskId = window.location.pathname.split('/').pop();
        
        this.eventSource = new EventSource(`/api/task/${taskId}/stream`);
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleUpdate(data);
        };
        
        this.eventSource.onerror = (error) => {
            console.error('SSE Error:', error);
            this.eventSource.close();
            
            // Try to reconnect after 5 seconds
            setTimeout(() => this.connectToUpdates(), 5000);
        };
    }
    
    handleUpdate(data) {
        // Update messages count
        const messagesEl = document.getElementById('messages-count');
        if (messagesEl) {
            messagesEl.textContent = data.messages_sent || 0;
        }
        
        // Update status
        const statusEl = document.getElementById('task-status');
        if (statusEl) {
            statusEl.textContent = data.status;
            statusEl.className = `badge badge-${data.status.toLowerCase()}`;
        }
        
        // Add to activity log
        if (data.message) {
            this.addToActivityLog(data);
        }
    }
    
    addToActivityLog(data) {
        const logContainer = document.getElementById('activity-log');
        if (!logContainer) return;
        
        const logItem = document.createElement('div');
        logItem.className = 'activity-item';
        logItem.innerHTML = `
            <div class="activity-time">${new Date().toLocaleTimeString()}</div>
            <div class="activity-message">${data.message}</div>
            ${data.level ? `<span class="badge badge-${data.level.toLowerCase()}">${data.level}</span>` : ''}
        `;
        
        logContainer.prepend(logItem);
        
        // Keep only last 50 items
        const items = logContainer.querySelectorAll('.activity-item');
        if (items.length > 50) {
            items[items.length - 1].remove();
        }
    }
}

// ===================== FORM VALIDATION =====================
class FormValidator {
    static init() {
        // Password toggle
        const toggleBtns = document.querySelectorAll('.toggle-password');
        toggleBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const input = this.previousElementSibling;
                const icon = this.querySelector('i');
                
                if (input.type === 'password') {
                    input.type = 'text';
                    icon.classList.remove('fa-eye');
                    icon.classList.add('fa-eye-slash');
                } else {
                    input.type = 'password';
                    icon.classList.remove('fa-eye-slash');
                    icon.classList.add('fa-eye');
                }
            });
        });
        
        // File input preview
        const fileInputs = document.querySelectorAll('input[type="file"]');
        fileInputs.forEach(input => {
            input.addEventListener('change', function() {
                const fileName = this.files[0]?.name || 'No file chosen';
                const displayEl = this.nextElementSibling;
                
                if (displayEl && displayEl.classList.contains('file-name')) {
                    displayEl.textContent = fileName;
                }
            });
        });
        
        // Character counter
        const textareas = document.querySelectorAll('textarea[data-maxlength]');
        textareas.forEach(textarea => {
            const maxLength = parseInt(textarea.dataset.maxlength);
            const counter = document.createElement('div');
            counter.className = 'char-counter';
            counter.style.cssText = 'font-size: 12px; color: #666; text-align: right; margin-top: 5px;';
            textarea.parentNode.appendChild(counter);
            
            const updateCounter = () => {
                const length = textarea.value.length;
                counter.textContent = `${length}/${maxLength}`;
                counter.style.color = length > maxLength ? '#ef4444' : '#666';
            };
            
            textarea.addEventListener('input', updateCounter);
            updateCounter();
        });
        
        // Auto-submit forms with single enter key
        document.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA') {
                const form = e.target.closest('form');
                if (form && !form.querySelector('textarea')) {
                    e.preventDefault();
                    form.requestSubmit();
                }
            }
        });
    }
}

// ===================== INITIALIZATION =====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Facebook Message Sender Initialized');
    
    // Initialize components based on page
    if (document.querySelector('.dashboard-page')) {
        new DashboardStats();
        new TaskManager();
    }
    
    if (document.querySelector('.task-page')) {
        new RealTimeUpdates();
    }
    
    if (document.querySelector('.cookie-management')) {
        new CookieManager();
    }
    
    // Initialize form validation
    FormValidator.init();
    
    // Add loading states to all buttons
    document.addEventListener('submit', function(e) {
        const form = e.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        
        if (submitBtn) {
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            submitBtn.disabled = true;
            
            // Re-enable button if form submission fails
            setTimeout(() => {
                if (submitBtn.disabled) {
                    submitBtn.innerHTML = submitBtn.dataset.originalText || 'Submit';
                    submitBtn.disabled = false;
                }
            }, 5000);
        }
    });
    
    // Add copy functionality to code elements
    document.querySelectorAll('code.copyable').forEach(code => {
        code.style.cursor = 'pointer';
        code.title = 'Click to copy';
        code.addEventListener('click', function() {
            Utils.copyToClipboard(this.textContent);
        });
    });
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
    
    // Auto-dismiss alerts
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});
