import os
import subprocess

def check_certbot_installed():
    """بررسی نصب بودن certbot"""
    try:
        subprocess.check_output(["which", "certbot"])
        return True
    except:
        return False

def install_certbot():
    """نصب خودکار certbot"""
    print("[+] Installing Certbot...")
    os.system("apt-get update && apt-get install -y certbot")

def get_ssl_certificate(domain, email="admin@alamor.local"):
    """گرفتن SSL رایگان با روش Standalone"""
    if not check_certbot_installed():
        install_certbot()
    
    print(f"[+] Requesting SSL for {domain}...")
    
    # نکته: پورت 80 باید خالی باشد. اگر پنل روی 80 است باید موقت استاپ شود.
    # ما از --http-01-port استفاده نمی‌کنیم چون پیچیده می‌شود.
    # فرض بر این است که پورت 80 آزاد است.
    
    cmd = f"certbot certonly --standalone -d {domain} --non-interactive --agree-tos -m {email} --keep-until-expiring"
    
    result = os.system(cmd)
    
    if result == 0:
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        key_path = f"/etc/letsencrypt/live/{domain}/privkey.pem"
        if os.path.exists(cert_path):
            return True, cert_path, key_path
    
    return False, None, None

def renew_certificates():
    """تمدید تمام گواهی‌ها"""
    os.system("certbot renew")