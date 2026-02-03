import os
import subprocess
import socket
import ssl
from core.config_loader import load_config, save_config

# مسیرها رو داینامیک نمی‌کنیم چون Nginx مسیرهای استاندارد داره
NGINX_SITE_PATH = "/etc/nginx/sites-available"
NGINX_ENABLED_PATH = "/etc/nginx/sites-enabled"
DEFAULT_PANEL_PORT = 2096  # پورت پیش‌فرض پنل (قابل تغییر)

def check_domain_dns(domain):
    try:
        # برای چک کردن IP پابلیک سرور
        cmd = "curl -s --max-time 5 https://api.ipify.org"
        server_ip = subprocess.check_output(cmd, shell=True).decode().strip()
        
        try:
            domain_ip = socket.gethostbyname(domain)
        except:
            return False, f"Domain {domain} not resolved"
        
        if server_ip == domain_ip:
            return True, "Match"
        else:
            return False, f"Mismatch: Domain->{domain_ip} | Server->{server_ip}"
    except Exception as e:
        return False, str(e)

def generate_letsencrypt_cert(domain, email="admin@alamor.local"):
    """دریافت SSL با متد Standalone تا نیاز به Nginx روی پورت 80 نباشه"""
    try:
        if not os.path.exists("/usr/bin/certbot"):
            os.system("apt-get update && apt-get install -y nginx certbot python3-certbot-nginx")
        
        # پورت 80 باید برای چند لحظه آزاد شه تا Certbot کار کنه
        os.system("systemctl stop nginx")
        
        # اگر تانلی روی پورت 80 دارید، باید موقت متوقف بشه یا از DNS Challenge استفاده کنید
        # فعلا فرض بر توقف سرویس‌های مزاحم است
        
        cmd = f"certbot certonly --standalone -d {domain} --email {email} --agree-tos --non-interactive"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # استارت دوباره
        os.system("systemctl start nginx")
        
        if result.returncode == 0:
            return True, "Certificate Issued Successfully!"
        else:
            # چک کنیم شاید سرتیفیکیت قبلا بوده
            if os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
                return True, "Certificate Already Exists"
            return False, f"Certbot Error: {result.stderr}"
    except Exception as e:
        os.system("systemctl start nginx")
        return False, str(e)

def setup_secure_panel_nginx(domain, secret_path):
    """
    کانفیگ ایزوله: پنل فقط روی پورت مخصوص خودش بالا میاد.
    پورت‌های 80 و 443 کاملا آزاد می‌مونن برای تانل‌ها.
    """
    try:
        # دریافت پورت ذخیره شده یا پیش‌فرض
        config = load_config()
        panel_port = config.get('panel_port', DEFAULT_PANEL_PORT)

        if not os.path.exists("/usr/sbin/nginx"):
            os.system("apt-get update && apt-get install -y nginx")

        # باز کردن پورت پنل در فایروال
        os.system(f"ufw allow {panel_port}/tcp")

        # 1. دریافت SSL
        if not os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
            res, msg = generate_letsencrypt_cert(domain)
            if not res: return False, msg

        # 2. کانفیگ Nginx (فقط پورت پنل)
        nginx_conf = f"""
server {{
    listen {panel_port} ssl http2;
    server_name {domain};
    
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    
    # تنظیمات امنیتی SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    root /var/www/html;
    index index.html;
    
    # Panel Proxy (مسیر مخفی)
    location /{secret_path}/ {{
        proxy_pass http://127.0.0.1:5050/{secret_path}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
    
    # هر درخواست دیگری روی این پورت را ریجکت کن (برای امنیت)
    location / {{
        return 404;
    }}
}}
"""
        # نوشتن کانفیگ
        with open(f"{NGINX_SITE_PATH}/{domain}", "w") as f:
            f.write(nginx_conf)
            
        # فعال‌سازی
        os.system(f"ln -sf {NGINX_SITE_PATH}/{domain} {NGINX_ENABLED_PATH}/")
        
        # حذف دیفالت برای جلوگیری از تداخل
        if os.path.exists(f"{NGINX_ENABLED_PATH}/default"):
            os.remove(f"{NGINX_ENABLED_PATH}/default")
            
        os.system("systemctl restart nginx")
        
        save_config('panel_domain', domain)
        save_config('panel_port', panel_port)
        
        return True, f"Panel secured on port {panel_port}"
    except Exception as e:
        return False, str(e)