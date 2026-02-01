from flask import Flask, redirect, url_for, jsonify
from core.database import init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
from routes.settings import settings_bp
from core.tasks import task_queue, task_status # <--- ایمپورت از فایل مشترک
import os
import threading
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)

def worker():
    """این تابع در پس‌زمینه اجرا می‌شود و تسک‌ها را انجام می‌دهد"""
    print(" [✓] Background Worker Started")
    while True:
        task_id, func, args = task_queue.get()
        try:
            print(f" [!] Processing Task: {task_id}")
            task_status[task_id] = {'progress': 5, 'status': 'running', 'log': 'Initializing process...'}
            
            for progress, log_msg in func(*args):
                task_status[task_id]['progress'] = progress
                task_status[task_id]['log'] = log_msg
                time.sleep(0.1)
            
            task_status[task_id]['progress'] = 100
            task_status[task_id]['status'] = 'completed'
            task_status[task_id]['log'] = 'Operation Completed Successfully.'
            print(f" [✓] Task {task_id} Finished")
            
        except Exception as e:
            print(f" [X] Task {task_id} Failed: {e}")
            task_status[task_id]['progress'] = 100
            task_status[task_id]['status'] = 'error'
            task_status[task_id]['log'] = f'Error: {str(e)}'
        finally:
            task_queue.task_done()

# اجرای ورکر در ترد جداگانه
threading.Thread(target=worker, daemon=True).start()

@app.route('/task-status/<task_id>')
def get_task_status(task_id):
    # اگر تسک پیدا نشد، یک وضعیت دیفالت برگردان تا JS ارور Undefined ندهد
    default = {'status': 'queued', 'progress': 0, 'log': 'Connecting to task manager...'}
    return jsonify(task_status.get(task_id, default))

# --- راه‌اندازی ---
init_db()
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tunnels_bp)
app.register_blueprint(settings_bp)

@app.route('/')
def root():
    return redirect(url_for('dashboard.index'))

if __name__ == '__main__':
    print("🚀 AlamorPanel started on http://0.0.0.0:5050")
    # نکته: use_reloader=False برای جلوگیری از اجرای دوبار ورکر در محیط دیباگ
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)