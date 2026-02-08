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
import logging

# --- LOGGING SETUP ---
# تنظیم لاگ‌ها برای نمایش در journalctl
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AlamorApp")

# بارگذاری تنظیمات
sys_config = load_config()
PANEL_PATH = sys_config.get('panel_path', '') 
URL_PREFIX = f"/{PANEL_PATH}" if PANEL_PATH else ""

app = Flask(__name__, static_url_path=f"{URL_PREFIX}/static")

# --- SECURITY ---
secret_key = sys_config.get('secret_key')
if not secret_key:
    secret_key = secrets.token_hex(32)
    save_config('secret_key', secret_key)
app.secret_key = secret_key

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'alamor_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False 

# --- TASK WORKER ---
def worker():
    logger.info("Task Worker Started")
    while True:
        try:
            task_id, func, args = task_queue.get()
            logger.info(f"Processing Task: {task_id}")
            task_status[task_id] = {'progress': 5, 'status': 'running', 'log': 'Starting...'}
            
            for progress, log_msg in func(*args):
                task_status[task_id]['progress'] = progress
                task_status[task_id]['log'] = log_msg
                logger.debug(f"Task {task_id}: {log_msg}")
            
            task_status[task_id]['progress'] = 100
            task_status[task_id]['status'] = 'completed'
            task_status[task_id]['log'] = 'Done!'
            logger.info(f"Task {task_id} Completed")
            
        except Exception as e:
            logger.error(f"Task Failed: {e}", exc_info=True)
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

# مقداردهی دیتابیس
try:
    init_db()
    logger.info("Database Initialized")
except Exception as e:
    logger.error(f"DB Init Failed: {e}")

# ثبت Blueprint ها
app.register_blueprint(auth_bp, url_prefix=f"{URL_PREFIX}/auth")
app.register_blueprint(dashboard_bp, url_prefix=f"{URL_PREFIX}/dashboard")
app.register_blueprint(tunnels_bp, url_prefix=f"{URL_PREFIX}/tunnel")
app.register_blueprint(settings_bp, url_prefix=f"{URL_PREFIX}/settings")
app.register_blueprint(domains_bp, url_prefix=f"{URL_PREFIX}/domains")

@app.route(f'{URL_PREFIX}/')
def root_redirect():
    return redirect(url_for('dashboard.index'))

if PANEL_PATH:
    @app.route('/')
    def global_root():
        return "Access Denied", 403

if __name__ == '__main__':
    logger.info("Starting AlamorTunnel Server on port 5050...")
    # فعال کردن Debug Mode برای دیدن خطاها
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)