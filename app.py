from flask import Flask, redirect, url_for, jsonify
from core.database import init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
from routes.settings import settings_bp
import os
import threading
import time
import queue

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- سیستم مدیریت تسک (Task Manager) ---
# صف برای نگهداری تسک‌های در انتظار
task_queue = queue.Queue()
# دیکشنری برای نگهداری وضعیت لحظه‌ای تسک‌ها
task_status = {} 

def worker():
    """این تابع در پس‌زمینه اجرا می‌شود و تسک‌ها را یکی‌یکی انجام می‌دهد"""
    while True:
        task_id, func, args = task_queue.get()
        try:
            # شروع تسک
            task_status[task_id] = {'progress': 5, 'status': 'running', 'log': 'Initializing process...'}
            
            # اجرای تابع نصب (که به صورت Generator است و مرحله‌به‌مرحله آپدیت می‌دهد)
            for progress, log_msg in func(*args):
                task_status[task_id]['progress'] = progress
                task_status[task_id]['log'] = log_msg
                # کمی تاخیر مصنوعی برای اینکه کاربر تغییرات را ببیند (اختیاری)
                time.sleep(0.5)
            
            # پایان موفقیت‌آمیز
            task_status[task_id]['progress'] = 100
            task_status[task_id]['status'] = 'completed'
            task_status[task_id]['log'] = 'Operation Completed Successfully.'
            
        except Exception as e:
            # پایان با خطا
            print(f"Task Error: {e}")
            task_status[task_id]['progress'] = 100
            task_status[task_id]['status'] = 'error'
            task_status[task_id]['log'] = f'Error: {str(e)}'
        finally:
            task_queue.task_done()

# اجرای ترد پس‌زمینه
threading.Thread(target=worker, daemon=True).start()

# API برای دریافت وضعیت تسک توسط جاوااسکریپت
@app.route('/task-status/<task_id>')
def get_task_status(task_id):
    return jsonify(task_status.get(task_id, {'status': 'not_found'}))

# --- راه‌اندازی برنامه ---
init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tunnels_bp)
app.register_blueprint(settings_bp)

@app.route('/')
def root():
    return redirect(url_for('dashboard.index'))

if __name__ == '__main__':
    print("🚀 AlamorPanel started on http://0.0.0.0:5050 with Async Task Manager")
    app.run(host='0.0.0.0', port=5050, debug=True, threaded=True)