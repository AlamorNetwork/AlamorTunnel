import queue

# این فایل تضمین می‌کند که همه بخش‌های برنامه از یک صف واحد استفاده می‌کنند
task_queue = queue.Queue()
task_status = {}

def init_task(task_id):
    """وضعیت اولیه را تنظیم می‌کند تا کاربر Undefined نبیند"""
    task_status[task_id] = {
        'progress': 0, 
        'status': 'queued', 
        'log': 'Waiting in queue...'
    }