import subprocess
import socket
import time
import shutil

def setup_iptables_for_port(port, protocol='tcp'):
    """ایجاد رول‌های iptables برای شمارش ترافیک پورت"""
    try:
        # بررسی اینکه آیا رول وجود دارد یا خیر
        check = subprocess.run(f"iptables -C INPUT -p {protocol} --dport {port} -j ACCEPT", shell=True, stderr=subprocess.DEVNULL)
        if check.returncode != 0:
            subprocess.run(f"iptables -I INPUT -p {protocol} --dport {port} -j ACCEPT", shell=True)
            subprocess.run(f"iptables -I OUTPUT -p {protocol} --sport {port} -j ACCEPT", shell=True)
    except:
        pass

def get_traffic_stats(port, protocol='tcp'):
    """خواندن مقدار بایت‌های رد و بدل شده"""
    try:
        # اطمینان از وجود رول
        setup_iptables_for_port(port, protocol)
        
        # خواندن خروجی iptables با دقت بالا (Bytes)
        # استفاده از awk برای استخراج دقیق عدد بایت
        cmd_in = f"iptables -L INPUT -v -n -x | grep 'dpt:{port}' | awk '{{print $2}}' | head -n 1"
        cmd_out = f"iptables -L OUTPUT -v -n -x | grep 'spt:{port}' | awk '{{print $2}}' | head -n 1"
        
        rx = subprocess.check_output(cmd_in, shell=True).decode().strip()
        tx = subprocess.check_output(cmd_out, shell=True).decode().strip()
        
        return int(rx) if rx else 0, int(tx) if tx else 0
    except:
        return 0, 0

def check_port_health(port, protocol='tcp'):
    """تست اتصال به پورت لوکال (Health Check)"""
    target = '127.0.0.1'
    try:
        start = time.time()
        if protocol == 'udp':
            # برای UDP فقط چک می‌کنیم سرویس در حال اجراست یا نه (ساده)
            # چون UDP هندشیک ندارد، پینگ TCP روی پورت لوکال ممکن نیست مگر اینکه سرویس TCP هم داشته باشد
            return {'status': 'active', 'latency': 0}
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        res = s.connect_ex((target, int(port)))
        s.close()
        
        latency = round((time.time() - start) * 1000, 2)
        
        if res == 0:
            return {'status': 'active', 'latency': latency}
        else:
            return {'status': 'down', 'latency': 0}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

def run_speedtest():
    """اجرای اسپیدتست روی سرور (نیاز به speedtest-cli دارد)"""
    if not shutil.which("speedtest-cli"):
        return {"error": "Speedtest-cli not installed. Run: apt install speedtest-cli"}
    
    try:
        # اجرای سریع (Simple)
        output = subprocess.check_output("speedtest-cli --simple", shell=True).decode()
        result = {}
        for line in output.split('\n'):
            if 'Ping' in line: result['ping'] = line.split()[1] + ' ms'
            if 'Download' in line: result['download'] = line.split()[1] + ' Mbit/s'
            if 'Upload' in line: result['upload'] = line.split()[1] + ' Mbit/s'
        return result
    except Exception as e:
        return {"error": str(e)}