import subprocess
import os

def check_domain_dns(domain):
    """بررسی اینکه آیا دامنه به سرور ما اشاره می‌کند یا نه"""
    try:
        # گرفتن IP سرور
        server_ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        # پینگ کردن دامنه
        domain_ip = subprocess.check_output(f"dig +short {domain}", shell=True).decode().strip()
        
        return server_ip == domain_ip
    except:
        return False

def generate_ssl_certificate(domain, email="admin@example.com"):
    """دریافت گواهی SSL با استفاده از Certbot"""
    try:
        # 1. توقف موقت Nginx برای جلوگیری از تداخل پورت 80
        os.system("systemctl stop nginx")
        
        # 2. دریافت گواهی (حالت Standalone برای راحتی)
        cmd = f"certbot certonly --standalone -d {domain} --email {email} --agree-tos --non-interactive"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # 3. روشن کردن دوباره Nginx
        os.system("systemctl start nginx")
        
        if result.returncode == 0:
            return True, f"Certificate generated for {domain}"
        else:
            return False, f"Certbot Error: {result.stderr}"
            
    except Exception as e:
        os.system("systemctl start nginx") # اطمینان از روشن شدن
        return False, str(e)

def get_cert_paths(domain):
    """مسیر فایل‌های سرتیفیکیت"""
    base_path = f"/etc/letsencrypt/live/{domain}"
    return {
        'cert': f"{base_path}/fullchain.pem",
        'key': f"{base_path}/privkey.pem"
    }