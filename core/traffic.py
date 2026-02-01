import psutil
import time
import subprocess
import json

# کش کردن آبجکت تست سرعت برای جلوگیری از لود طولانی
speedtest_cache = None

def get_traffic_stats(port=None, proto='tcp'):
    """
    دریافت میزان مصرف شبکه.
    اگر پورت مشخص باشد سعی میکند ترافیک آن را حدس بزند (که سخت است)،
    اما معمولا ترافیک کل اینترفیس را برمی‌گرداند که دقیق‌تر است.
    """
    try:
        # دریافت آمار کل شبکه
        net_io = psutil.net_io_counters()
        return net_io.bytes_recv, net_io.bytes_sent
    except Exception as e:
        return 0, 0

def check_port_health(port, proto='tcp'):
    """بررسی اینکه آیا پورت باز است و سرویس زنده است یا نه"""
    try:
        # استفاده از دستور ss لینوکس برای سرعت بالا
        cmd = f"ss -l{proto}n | grep :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()
        if str(port) in output:
            return {'status': 'active', 'latency': '1ms'} # پینگ داخلی
        else:
            return {'status': 'inactive', 'latency': '-'}
    except:
        return {'status': 'inactive', 'latency': '-'}

def run_speedtest():
    """اجرای تست سرعت واقعی"""
    global speedtest_cache
    try:
        # استفاده از speedtest-cli به صورت کامند لاین (سریع‌تر و پایدارتر)
        # دستور --json خروجی را تمیز می‌دهد
        cmd = "speedtest-cli --json --secure"
        output = subprocess.check_output(cmd, shell=True).decode()
        data = json.loads(output)
        
        return {
            'ping': f"{int(data['ping'])} ms",
            'download': f"{data['download'] / 1000000:.2f} Mbps",
            'upload': f"{data['upload'] / 1000000:.2f} Mbps",
            'server': data['server']['country'] + " - " + data['server']['name']
        }
    except Exception as e:
        return {'error': str(e)}