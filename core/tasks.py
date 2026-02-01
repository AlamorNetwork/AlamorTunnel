import queue

# صف مشترک برای تمام بخش‌های برنامه
task_queue = queue.Queue()

# وضعیت تسک‌ها
task_status = {}

def init_task(task_id):
    """وضعیت اولیه را تنظیم می‌کند تا کاربر Undefined نبیند"""
    task_status[task_id] = {
        'progress': 0, 
        'status': 'queued', 
        'log': 'Waiting in queue...'
    }