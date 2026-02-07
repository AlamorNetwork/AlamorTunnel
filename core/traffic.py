import psutil
import time
import subprocess
import re
import socket
import requests
import shutil
def get_traffic_stats(port=None, proto='tcp'):
    """
    دریافت آمار مصرف شبکه (RX/TX)
    اگر پورت مشخص شود، سعی می‌کند ترافیک آن پورت را جدا کند (نیاز به دسترسی root و nethogs دارد که پیچیده است)
    برای سادگی، فعلاً ترافیک کل اینترفیس اصلی را برمی‌گرداند.
    """
    # دریافت ترافیک کل سیستم
    io = psutil.net_io_counters()
    return io.bytes_recv, io.bytes_sent

def check_port_health(port):
    """بررسی اینکه آیا پورتی در حال گوش دادن است یا خیر"""
    try:
        # استفاده از ss برای سرعت بیشتر
        result = subprocess.check_output(f"ss -tulpn | grep :{port}", shell=True).decode()
        return bool(result.strip())
    except:
        return False

def check_connectivity(target_ip, port=80, timeout=3):
    """
    بررسی اتصال به سرور خارج با تلاش برای ایجاد سوکت واقعی
    """
    try:
        # تلاش برای اتصال TCP
        sock = socket.create_connection((target_ip, int(port)), timeout=timeout)
        sock.close()
        return True, "Connected"
    except socket.timeout:
        return False, "Timeout"
    except ConnectionRefusedError:
        # اگر ریفیوز داد یعنی سرور هست ولی پورت بسته است (پس سرور زنده است)
        return True, "Port Closed but Server Alive"
    except Exception as e:
        return False, str(e)

def run_advanced_speedtest(target_ip=None, local_port=None):
    """
    تست سرعت کامل: Ping, Download, Upload
    """
    result = {
        'ping': '0',
        'download': '0',
        'upload': '0',
        'connectivity': False,
        'message': ''
    }

    # 1. Ping Test
    try:
        ping_target = target_ip if target_ip else "8.8.8.8"
        # پینگ 4 تایی
        ping_out = subprocess.check_output(f"ping -c 4 -q {ping_target}", shell=True).decode()
        # استخراج میانگین (avg)
        avg_ping = re.search(r'(\d+\.\d+)/(\d+\.\d+)/', ping_out)
        if avg_ping:
            result['ping'] = avg_ping.group(2) # مقدار avg
    except:
        result['ping'] = "Timeout"

    # 2. Connectivity Check (اگر IP تانل داریم)
    if target_ip:
        is_connected, msg = check_connectivity(target_ip, 443) # پیش‌فرض پورت 443
        result['connectivity'] = is_connected
        result['message'] = msg
    else:
        # تست اتصال عمومی به اینترنت
        try:
            requests.get("https://www.google.com", timeout=3)
            result['connectivity'] = True
            result['message'] = "Internet OK"
        except:
            result['connectivity'] = False
            result['message'] = "No Internet"

    # 3. Download Speed (استفاده از Cloudflare)
    try:
        # دانلود فایل 10 مگابایتی و اندازه گیری سرعت
        # فرمت خروجی curl: سرعت دانلود در ستون خاصی است. ما از write-out استفاده می‌کنیم
        cmd = "curl -L -w '%{speed_download}' -o /dev/null -s https://speed.cloudflare.com/__down?bytes=10000000"
        speed_bps = float(subprocess.check_output(cmd, shell=True).decode().strip())
        result['download'] = round(speed_bps * 8 / 1000000, 2) # تبدیل بایت/ثانیه به مگابیت/ثانیه
    except Exception as e:
        print(f"DL Error: {e}")
        result['download'] = "Error"

    # 4. Upload Speed (تست آپلود کوچک)
    try:
        # آپلود به سرویس‌هایی که اجازه POST می‌دهند (مثل dslreports یا speedtest-cli اگر نصب باشد)
        # چون curl آپلود استاندارد سخت است، از یک فایل تست کوچک به یک API عمومی استفاده می‌کنیم
        # یا اگر speedtest-cli نصب است از آن استفاده می‌کنیم
        if shutil.which("speedtest"): # اگر speedtest-cli نصب بود
             out = subprocess.check_output("speedtest --simple --secure", shell=True).decode()
             # پارس کردن خروجی speedtest-cli
             for line in out.split('\n'):
                 if "Upload:" in line:
                     result['upload'] = line.split()[1]
        else:
            # فال‌بک: آپلود فایل 1 مگابایتی به transfer.sh (یا هر سرویس مشابه)
            # ایجاد فایل 1MB    
            subprocess.run("dd if=/dev/zero of=/tmp/test.upload bs=1M count=1", shell=True)
            cmd = "curl -w '%{speed_upload}' -F 'file=@/tmp/test.upload' -o /dev/null -s https://transfer.sh/"
            speed_bps = float(subprocess.check_output(cmd, shell=True).decode().strip())
            result['upload'] = round(speed_bps * 8 / 1000000, 2)
    except:
        result['upload'] = "N/A" # اگر آپلود فیلتر بود یا خطا داد

    return result