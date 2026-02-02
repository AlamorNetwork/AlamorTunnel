import os
import subprocess
import socket
import urllib.request
import ssl
from core.config_loader import load_config, save_config

CERT_DIR = "/root/certs"
NGINX_SITE_PATH = "/etc/nginx/sites-available"
NGINX_ENABLED_PATH = "/etc/nginx/sites-enabled"
PANEL_PORT = 2096  # پورت اختصاصی پنل (مثل سنایی)

def get_server_public_ip():
    providers = ['https://api.ipify.org', 'https://ifconfig.me/ip', 'https://icanhazip.com']
    for url in providers:
        try:
            ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(url, timeout=5, context=ctx) as r:
                return r.read().decode('utf-8').strip()
        except: continue
    return None

def generate_self_signed_cert(domain_or_ip="127.0.0.1"):
    if not os.path.exists(CERT_DIR): os.makedirs(CERT_DIR)
    key_file = f"{CERT_DIR}/server.key"
    crt_file = f"{CERT_DIR}/server.crt"
    if os.path.exists(crt_file) and os.path.exists(key_file): return True, crt_file, key_file
    try:
        subprocess.run(f"openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {crt_file} -days 3650 -nodes -subj '/CN={domain_or_ip}'", shell=True, check=True)
        return True, crt_file, key_file
    except Exception as e: return False, str(e), None

def setup_secure_panel_nginx(domain, secret_path):
    """
    معماری سنایی:
    - پنل: https://domain:2096/secret/
    - تانل: https://domain:443/ (خالی برای استفاده بعدی)
    """
    try:
        if not os.path.exists("/usr/sbin/nginx"):
            os.system("apt-get update && apt-get install -y nginx certbot python3-certbot-nginx")

        # باز کردن پورت پنل در فایروال
        os.system(f"ufw allow {PANEL_PORT}/tcp")
        os.system("ufw allow 80/tcp")
        os.system("ufw allow 443/tcp")

        # 1. دریافت SSL
        if not os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
            os.system("systemctl stop nginx")
            cmd = f"certbot certonly --standalone -d {domain} --email admin@alamor.local --agree-tos --non-interactive"
            subprocess.run(cmd, shell=True)
            os.system("systemctl start nginx")

        # 2. کانفیگ Nginx (دو سرور بلاک جداگانه)
        nginx_conf = f"""
# =========================================
# BLOCK 1: PANEL (Port {PANEL_PORT})
# =========================================
server {{
    listen {PANEL_PORT} ssl http2;
    server_name {domain};
    
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    
    root /var/www/html;
    index index.html;
    
    # Panel Proxy
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
    
    # Block everything else on this port
    location / {{
        return 404;
    }}
}}

# =========================================
# BLOCK 2: TUNNEL ROOT (Port 443)
# =========================================
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
    
    # Placeholder for Root Tunnel
    location / {{
        default_type text/html;
        return 200 '<h1>Tunnel Endpoint Ready</h1>';
    }}
}}
"""
        with open(f"{NGINX_SITE_PATH}/{domain}", "w") as f: f.write(nginx_conf)
        os.system(f"ln -sf {NGINX_SITE_PATH}/{domain} {NGINX_ENABLED_PATH}/")
        os.system(f"rm -f {NGINX_ENABLED_PATH}/default")
        os.system("systemctl restart nginx")
        
        save_config('panel_domain', domain)
        save_config('panel_port', PANEL_PORT)
        return True, f"Panel moved to Port {PANEL_PORT}"
    except Exception as e: return False, str(e)

def set_root_tunnel(target_port):
    """
    تنظیم تانل روی پورت 443 (Root) بدون دستکاری پنل
    """
    config = load_config()
    domain = config.get('panel_domain')
    secret_path = config.get('panel_path', 'admin')
    
    if not domain: return False, "Domain not configured"
    
    # بازنویسی کانفیگ با تانل جدید روی 443
    nginx_conf = f"""
# PANEL BLOCK (Untouched)
server {{
    listen {PANEL_PORT} ssl http2;
    server_name {domain};
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    
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
}}

# TUNNEL BLOCK (Updated)
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
    
    # Root Tunnel Proxy
    location / {{
        proxy_pass http://127.0.0.1:{target_port};
        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}
"""
    try:
        with open(f"{NGINX_SITE_PATH}/{domain}", "w") as f: f.write(nginx_conf)
        os.system("systemctl reload nginx")
        return True, "Tunnel set to Root (443)"
    except Exception as e: return False, str(e)