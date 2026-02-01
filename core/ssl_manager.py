import os
import subprocess

CERT_DIR = "/root/certs"
KEY_FILE = f"{CERT_DIR}/server.key"
CSR_FILE = f"{CERT_DIR}/server.csr"
CRT_FILE = f"{CERT_DIR}/server.crt"

def generate_self_signed_cert(domain_or_ip="127.0.0.1"):
    """تولید سرتیفیکیت داخلی برای Backhaul و استفاده‌های بدون دامنه"""
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)

    if os.path.exists(CRT_FILE) and os.path.exists(KEY_FILE):
        return True, CRT_FILE, KEY_FILE

    try:
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-out", KEY_FILE, "-pkeyopt", "rsa_keygen_bits:2048"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subj = f"/C=US/ST=State/L=City/O=Alamor/CN={domain_or_ip}"
        subprocess.run(
            ["openssl", "req", "-new", "-key", KEY_FILE, "-out", CSR_FILE, "-subj", subj],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        subprocess.run(
            ["openssl", "x509", "-req", "-in", CSR_FILE, "-signkey", KEY_FILE, "-out", CRT_FILE, "-days", "3650"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True, CRT_FILE, KEY_FILE
    except Exception as e:
        return False, str(e), None

def check_domain_dns(domain):
    """بررسی اینکه آیا دامنه به سرور ما اشاره می‌کند"""
    try:
        server_ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        domain_ip = subprocess.check_output(f"dig +short {domain}", shell=True).decode().strip()
        return server_ip == domain_ip
    except:
        return False

def generate_letsencrypt_cert(domain, email="admin@alamor.local"):
    """دریافت سرتیفیکیت معتبر با Certbot"""
    try:
        # نصب پیشنیازها اگر نصب نباشند
        if not os.path.exists("/usr/bin/certbot"):
             os.system("apt-get update && apt-get install -y nginx certbot python3-certbot-nginx")

        os.system("systemctl stop nginx") # آزادسازی پورت 80
        
        cmd = f"certbot certonly --standalone -d {domain} --email {email} --agree-tos --non-interactive"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        os.system("systemctl start nginx")
        
        if result.returncode == 0:
            return True, "Certificate Issued Successfully!"
        else:
            return False, f"Certbot Error: {result.stderr}"
    except Exception as e:
        os.system("systemctl start nginx")
        return False, str(e)

def setup_fake_site_nginx(domain, template_type="game"):
    """راه اندازی سایت فیک روی Nginx با SSL"""
    try:
        html_dir = "/var/www/html"
        os.makedirs(html_dir, exist_ok=True)
        
        # HTML ساده برای سایت فیک
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Welcome</title><style>body{font-family:sans-serif;text-align:center;padding:50px;background:#f0f0f0;}</style></head>
        <body><h1>Site Under Maintenance</h1><p>We are currently performing scheduled maintenance.</p></body>
        </html>
        """
        with open(f"{html_dir}/index.html", "w") as f:
            f.write(html_content)

        # کانفیگ Nginx
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

    location / {{
        try_files $uri $uri/ =404;
    }}
}}
"""
        with open(f"/etc/nginx/sites-available/{domain}", "w") as f:
            f.write(nginx_conf)
            
        os.system(f"ln -sf /etc/nginx/sites-available/{domain} /etc/nginx/sites-enabled/")
        os.system("rm -f /etc/nginx/sites-enabled/default")
        os.system("systemctl restart nginx")
        return True, "Fake site deployed!"
    except Exception as e:
        return False, str(e)