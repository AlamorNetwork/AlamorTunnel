from flask import Flask, redirect, url_for, jsonify
from core.database import init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
from routes.settings import settings_bp
from core.tasks import task_queue, task_status
import os
import threading
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tunnels_bp)
app.register_blueprint(settings_bp)

@app.route('/')
def root(): return redirect(url_for('dashboard.index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True, use_reloader=False)