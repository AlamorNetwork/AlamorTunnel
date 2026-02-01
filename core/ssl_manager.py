import os
import subprocess
import socket
import urllib.request
import ssl
from core.config_loader import save_config

CERT_DIR = "/root/certs"
KEY_FILE = f"{CERT_DIR}/server.key"
CSR_FILE = f"{CERT_DIR}/server.csr"
CRT_FILE = f"{CERT_DIR}/server.crt"
def get_server_public_ip():
    """دریافت آی‌پی سرور از چندین منبع مختلف برای اطمینان"""
    providers = [
        'https://api.ipify.org',
        'https://ifconfig.me/ip',
        'https://icanhazip.com'
    ]
    for url in providers:
        try:
            # غیرفعال کردن بررسی SSL برای سرعت و جلوگیری از خطای سرتیفیکیت در برخی سرورها
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(url, timeout=5, context=ctx) as response:
                ip = response.read().decode('utf-8').strip()
                if len(ip.split('.')) == 4: # اعتبارسنجی فرمت IPv4
                    return ip
        except:
            continue
    return None

def check_domain_dns(domain):
    """بررسی دقیق DNS با گزارش علت خطا"""
    try:
        # 1. گرفتن آی‌پی سرور
        server_ip = get_server_public_ip()
        if not server_ip:
            return False, "Could not detect Server Public IP (Network Error)"

        # 2. گرفتن آی‌پی دامنه (Resolve)
        try:
            domain_ip = socket.gethostbyname(domain)
        except socket.gaierror:
            return False, f"Domain {domain} could not be resolved (NXDOMAIN)"

        # 3. مقایسه
        if server_ip == domain_ip:
            return True, "Match"
        else:
            return False, f"Mismatch: Domain->{domain_ip} | Server->{server_ip}"

    except Exception as e:
        return False, f"System Error: {str(e)}"

# --- بقیه توابع بدون تغییر باقی می‌مانند ---
def generate_self_signed_cert(domain_or_ip="127.0.0.1"):
    if not os.path.exists(CERT_DIR): os.makedirs(CERT_DIR)
    if os.path.exists(CRT_FILE) and os.path.exists(KEY_FILE): return True, CRT_FILE, KEY_FILE
    try:
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-out", KEY_FILE, "-pkeyopt", "rsa_keygen_bits:2048"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subj = f"/C=US/ST=State/L=City/O=Alamor/CN={domain_or_ip}"
        subprocess.run(["openssl", "req", "-new", "-key", KEY_FILE, "-out", CSR_FILE, "-subj", subj], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["openssl", "x509", "-req", "-in", CSR_FILE, "-signkey", KEY_FILE, "-out", CRT_FILE, "-days", "3650"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, CRT_FILE, KEY_FILE
    except Exception as e: return False, str(e), None

def generate_letsencrypt_cert(domain, email="admin@alamor.local"):
    try:
        if not os.path.exists("/usr/bin/certbot"): os.system("apt-get update && apt-get install -y nginx certbot python3-certbot-nginx")
        os.system("systemctl stop nginx")
        cmd = f"certbot certonly --standalone -d {domain} --email {email} --agree-tos --non-interactive"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        os.system("systemctl start nginx")
        if result.returncode == 0: return True, "Certificate Issued Successfully!"
        else: return False, f"Certbot Error: {result.stderr}"
    except Exception as e:
        os.system("systemctl start nginx")
        return False, str(e)

def setup_fake_site_nginx(domain):
    try:
        html_dir = "/var/www/html"
        os.makedirs(html_dir, exist_ok=True)
        with open(f"{html_dir}/index.html", "w") as f:
            f.write("<!DOCTYPE html><html><head><title>Welcome</title></head><body><h1>Maintenance Mode</h1></body></html>")
        nginx_conf = f"""
server {{
    listen 80;
    server_name {domain};
    return 301 https://$host$request_uri;
}}
server {{
    listen 443 ssl;
    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    root /var/www/html;
    index index.html;
    location / {{ try_files $uri $uri/ =404; }}
}}
"""
        with open(f"/etc/nginx/sites-available/{domain}", "w") as f: f.write(nginx_conf)
        os.system(f"ln -sf /etc/nginx/sites-available/{domain} /etc/nginx/sites-enabled/")
        os.system("rm -f /etc/nginx/sites-enabled/default")
        os.system("systemctl restart nginx")
        return True, "Fake site deployed!"
    except Exception as e: return False, str(e)


def setup_secure_panel_nginx(domain, secret_path):
    """
    کانفیگ حرفه‌ای Nginx:
    - مسیر / : سایت فیک
    - مسیر /secret_path/ : پنل اصلی (پروکسی به پورت 5050)
    """
    try:
        html_dir = "/var/www/html"
        os.makedirs(html_dir, exist_ok=True)
        
        # 1. ساخت سایت فیک (صفحه تعمیرات شیک)
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Site Maintenance</title>
            <style>
                body { text-align: center; padding: 150px; font-family: sans-serif; background: #f2f2f2; color: #333; }
                h1 { font-size: 50px; }
                article { display: block; text-align: left; width: 650px; margin: 0 auto; }
            </style>
        </head>
        <body>
            <article>
                <h1>We&rsquo;ll be back soon!</h1>
                <div><p>Sorry for the inconvenience but we&rsquo;re performing some maintenance at the moment.</p></div>
            </article>
        </body>
        </html>
        """
        with open(f"{html_dir}/index.html", "w") as f:
            f.write(html_content)

        # 2. کانفیگ Nginx با Reverse Proxy
        # نکته مهم: هدرهای امنیتی اضافه شده
        nginx_conf = f"""
server {{
    listen 80;
    server_name {domain};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {domain};

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000" always;

    root /var/www/html;
    index index.html;

    # 1. Fake Site on Root
    location / {{
        try_files $uri $uri/ =404;
    }}

    # 2. Real Panel on Secret Path
    location /{secret_path}/ {{
        proxy_pass http://127.0.0.1:5050/{secret_path}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        # WebSocket Support (For terminals etc)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
"""
        with open(f"/etc/nginx/sites-available/{domain}", "w") as f:
            f.write(nginx_conf)
            
        os.system(f"ln -sf /etc/nginx/sites-available/{domain} /etc/nginx/sites-enabled/")
        os.system("rm -f /etc/nginx/sites-enabled/default")
        os.system("systemctl restart nginx")
        
        # ذخیره مسیر در کانفیگ سیستم
        save_config('panel_path', secret_path)
        
        return True, f"/etc/letsencrypt/live/{domain}/"
    except Exception as e:
        return False, str(e)