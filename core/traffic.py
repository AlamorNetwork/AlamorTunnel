import psutil
import subprocess
import json
import re

def get_traffic_stats(port=None, proto='tcp'):
    """
    دریافت میزان مصرف شبکه کل سرور.
    """
    try:
        net_io = psutil.net_io_counters()
        return net_io.bytes_recv, net_io.bytes_sent
    except Exception as e:
        return 0, 0

def check_port_health(port, proto='tcp'):
    """بررسی سلامت پورت با استفاده از ss"""
    try:
        cmd = f"ss -l{proto}n | grep :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()
        if str(port) in output:
            return {'status': 'active', 'latency': 'Online'}
        else:
            return {'status': 'inactive', 'latency': 'Down'}
    except:
        return {'status': 'inactive', 'latency': 'Down'}

def run_advanced_speedtest(target_ip=None, local_port=None):
    """
    اجرای تست سرعت هوشمند:
    1. پینگ: اگر IP سرور خارج داده شود، به آن پینگ می‌زند (تأخیر تانل).
    2. دانلود: یک فایل 10MB از کلادفلر دانلود می‌کند تا ظرفیت شبکه سرور را بسنجد.
    """
    result = {
        'ping': 'N/A',
        'download': 'N/A',
        'upload': 'N/A'
    }

    # 1. تست پینگ (Latency)
    try:
        # اگر آی‌پی هدف (سرور خارج) داریم به آن پینگ بزن، اگر نه به گوگل
        dest = target_ip if target_ip else "8.8.8.8"
        ping_cmd = f"ping -c 3 {dest} | tail -1 | awk '{{print $4}}' | cut -d '/' -f 2"
        ping_out = subprocess.check_output(ping_cmd, shell=True, timeout=5).decode().strip()
        if ping_out:
            result['ping'] = f"{float(ping_out):.0f} ms"
        else:
            result['ping'] = "Timeout"
    except:
        result['ping'] = "Timeout"

    # 2. تست دانلود (Throughput)
    try:
        # دانلود از کلادفلر (معمولاً در ایران باز است و سرعت واقعی را نشان می‌دهد)
        # تایم‌اوت 15 ثانیه برای جلوگیری از گیر کردن پنل
        dl_cmd = "curl -L -o /dev/null -w '%{speed_download}' --max-time 15 http://speed.cloudflare.com/__down?bytes=10000000"
        
        # اگر پورت پراکسی (SOCKS5) داده شده باشد، از داخل تانل تست کن (اختیاری)
        # فعلاً مستقیم تست می‌کنیم چون کانفیگ‌های فعلی SOCKS نیستند
        
        dl_out = subprocess.check_output(dl_cmd, shell=True).decode().strip()
        
        # تبدیل بایت/ثانیه به مگابیت/ثانیه
        speed_bps = float(dl_out)
        speed_mbps = (speed_bps * 8) / (1024 * 1024)
        result['download'] = f"{speed_mbps:.2f} Mbps"
        
    except Exception as e:
        result['download'] = "Error"

    # 3. تست آپلود (N/A)
    # تست آپلود دقیق بدون سرور مقصد دشوار است
    result['upload'] = "N/A"

    return result