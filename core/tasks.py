import queue

# صف مشترک برای مدیریت کارهای پس‌زمینه
task_queue = queue.Queue()
task_status = {}

def init_task(task_id):
    """جلوگیری از نمایش Undefined در لحظه اول"""
    task_status[task_id] = {
        'progress': 0, 
        'status': 'queued', 
        'log': 'Waiting in queue...'
    }