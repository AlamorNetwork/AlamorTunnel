import psutil
import time
import subprocess
import json
import re

def get_traffic_stats(port=None, proto='tcp'):
    """
    دریافت میزان مصرف شبکه کل سرور (دقیق‌ترین روش).
    """
    try:
        net_io = psutil.net_io_counters()
        return net_io.bytes_recv, net_io.bytes_sent
    except Exception as e:
        return 0, 0

def check_port_health(port, proto='tcp'):
    """بررسی سلامت پورت و سرویس"""
    try:
        # استفاده از ss برای سرعت بالا
        cmd = f"ss -l{proto}n | grep :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()
        if str(port) in output:
            return {'status': 'active', 'latency': 'Online'}
        else:
            return {'status': 'inactive', 'latency': 'Down'}
    except:
        return {'status': 'inactive', 'latency': 'Down'}

def run_speedtest():
    """
    اجرای تست سرعت بهینه شده برای ایران:
    به جای speedtest-cli که فیلتر است، از curl و ping سیستم استفاده می‌کند.
    """
    try:
        result = {}
        
        # 1. تست پینگ (به گوگل DNS)
        try:
            # ارسال 3 پکت و گرفتن میانگین
            ping_cmd = "ping -c 3 8.8.8.8 | tail -1 | awk '{print $4}' | cut -d '/' -f 2"
            ping_out = subprocess.check_output(ping_cmd, shell=True).decode().strip()
            result['ping'] = f"{float(ping_out):.0f} ms"
        except:
            result['ping'] = "Timeout"

        # 2. تست سرعت دانلود (از Cloudflare)
        try:
            # دانلود 10 مگابایت و اندازه گیری سرعت
            # فرمت خروجی: سرعت به بایت بر ثانیه
            dl_cmd = "curl -L -o /dev/null -w '%{speed_download}' --max-time 15 http://speed.cloudflare.com/__down?bytes=10000000"
            dl_out = subprocess.check_output(dl_cmd, shell=True).decode().strip()
            
            # تبدیل بایت/ثانیه به مگابیت/ثانیه (bps * 8 / 1,000,000)
            speed_bps = float(dl_out)
            speed_mbps = (speed_bps * 8) / (1024 * 1024)
            result['download'] = f"{speed_mbps:.2f} Mbps"
        except:
            result['download'] = "Error"

        # 3. آپلود (تخمین یا Skip)
        # تست دقیق آپلود بدون سرور مقصد دشوار است، فعلاً N/A میزنیم تا سریع باشد
        result['upload'] = "N/A"
        
        # نام سرور (دریافت نام هاست خودمان)
        try:
            hostname = subprocess.check_output("hostname", shell=True).decode().strip()
            result['server'] = f"Local: {hostname}"
        except:
            result['server'] = "Local Server"

        return result

    except Exception as e:
        return {'error': str(e)}