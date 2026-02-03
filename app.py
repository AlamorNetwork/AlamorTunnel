from flask import Flask, redirect, url_for, jsonify
from core.database import init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
from routes.settings import settings_bp
from routes.domains import domains_bp
from core.tasks import task_queue, task_status
from core.config_loader import load_config, save_config
from datetime import timedelta
import os
import threading
import secrets

# بارگذاری تنظیمات
sys_config = load_config()
PANEL_PATH = sys_config.get('panel_path', '') 
URL_PREFIX = f"/{PANEL_PATH}" if PANEL_PATH else ""

app = Flask(__name__, static_url_path=f"{URL_PREFIX}/static")

# --- SECURITY CONFIG (FIXED) ---
# 1. Secret Key Persistence: جلوگیری از پریدن لاگین با ریستارت
secret_key = sys_config.get('secret_key')
if not secret_key:
    secret_key = secrets.token_hex(32)
    save_config('secret_key', secret_key)
app.secret_key = secret_key

# 2. Session Config
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'alamor_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# غیرفعال کردن موقت Secure برای حل مشکل لوپ لاگین در حالت IP
app.config['SESSION_COOKIE_SECURE'] = False 

# --- TASK SYSTEM ---
def worker():
    while True:
        try:
            task_id, func, args = task_queue.get()
            task_status[task_id] = {'progress': 5, 'status': 'running', 'log': 'Starting...'}
            for progress, log_msg in func(*args):
                task_status[task_id]['progress'] = progress
                task_status[task_id]['log'] = log_msg
            task_status[task_id]['progress'] = 100
            task_status[task_id]['status'] = 'completed'
            task_status[task_id]['log'] = 'Done!'
        except Exception as e:
            if 'task_id' in locals():
                task_status[task_id]['progress'] = 100
                task_status[task_id]['status'] = 'error'
                task_status[task_id]['log'] = f'Error: {str(e)}'
        finally:
            if 'task_id' in locals(): task_queue.task_done()

threading.Thread(target=worker, daemon=True).start()

@app.route('/task-status/<task_id>')
def get_task_status(task_id):
    return jsonify(task_status.get(task_id, {'status': 'queued', 'progress': 0}))

init_db()

# --- BLUEPRINTS ---
app.register_blueprint(auth_bp, url_prefix=f"{URL_PREFIX}/auth")
app.register_blueprint(dashboard_bp, url_prefix=f"{URL_PREFIX}/dashboard")
app.register_blueprint(tunnels_bp, url_prefix=f"{URL_PREFIX}/tunnel")
app.register_blueprint(settings_bp, url_prefix=f"{URL_PREFIX}/settings")
app.register_blueprint(domains_bp, url_prefix=f"{URL_PREFIX}/domains")

# ریدایرکت روت
@app.route(f'{URL_PREFIX}/')
def root_redirect():
    return redirect(url_for('dashboard.index'))

if PANEL_PATH:
    @app.route('/')
    def global_root():
        return "Access Denied", 403

if __name__ == '__main__':
    # Debug=False برای محیط پروداکشن
    app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)