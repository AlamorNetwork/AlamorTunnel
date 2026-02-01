import subprocess
import concurrent.futures
import random

# لیست کوتاهی از رنج‌های کلاودفلر (برای نمونه)
# در نسخه واقعی می‌تونی کل رنج‌ها رو بذاری
CF_RANGES = [
    "104.16.0.0/24", "104.17.0.0/24", "104.18.0.0/24", 
    "104.19.0.0/24", "104.20.0.0/24", "104.21.0.0/24",
    "172.64.0.0/24", "172.67.0.0/24"
]

def check_ip(ip, domain, timeout=1):
    """تست اتصال به یک IP خاص با SNI دامنه خودمان"""
    try:
        # استفاده از curl برای تست واقعی هندشیک SSL
        # --resolve دامنه رو مجبور میکنه به این IP وصل شه
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' --connect-timeout {timeout} --max-time {timeout + 1} --resolve {domain}:443:{ip} https://{domain}"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.stdout.strip() in ["200", "301", "302", "403", "404"]:
            return True, ip
        return False, ip
    except:
        return False, ip

def scan_for_clean_ip(domain, max_threads=10, limit=5):
    """اسکن رندوم برای پیدا کردن IP تمیز"""
    found_ips = []
    # تولید 50 آی‌پی رندوم از رنج‌ها برای تست سریع
    test_ips = []
    for _ in range(50):
        subnet = random.choice(CF_RANGES)
        base = ".".join(subnet.split('.')[:3])
        last = random.randint(1, 254)
        test_ips.append(f"{base}.{last}")

    logs = []
    logs.append(f"Generated {len(test_ips)} targets from Cloudflare pool...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
        future_to_ip = {executor.submit(check_ip, ip, domain): ip for ip in test_ips}
        
        for future in concurrent.futures.as_completed(future_to_ip):
            success, ip = future.result()
            if success:
                latency = 0 # میشه پینگ هم گرفت ولی فعلا ساده‌ش کردیم
                found_ips.append({'ip': ip, 'latency': 'LOW'})
                logs.append(f"HIT: {ip} is responsive!")
                if len(found_ips) >= limit:
                    break
            else:
                pass 
                # logs.append(f"MISS: {ip} timed out") # لاگ شلوغ نشه

    return found_ips, logs