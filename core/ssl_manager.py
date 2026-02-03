import os
import subprocess
import socket
import ssl
from core.config_loader import load_config, save_config

# Constants
CERT_DIR = "/root/certs"
NGINX_SITE_PATH = "/etc/nginx/sites-available"
NGINX_ENABLED_PATH = "/etc/nginx/sites-enabled"
DEFAULT_PANEL_PORT = 2096

def check_domain_dns(domain):
    """Checks if the domain resolves to the server's public IP."""
    try:
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
    """Obtains a LetsEncrypt certificate using Standalone mode (frees port 80 momentarily)."""
    try:
        if not os.path.exists("/usr/bin/certbot"):
            os.system("apt-get update && apt-get install -y nginx certbot python3-certbot-nginx")
        
        # Stop Nginx to free up port 80 for the challenge
        os.system("systemctl stop nginx")
        
        cmd = f"certbot certonly --standalone -d {domain} --email {email} --agree-tos --non-interactive"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # Restart Nginx
        os.system("systemctl start nginx")
        
        if result.returncode == 0:
            return True, "Certificate Issued Successfully!"
        else:
            if os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
                return True, "Certificate Already Exists"
            return False, f"Certbot Error: {result.stderr}"
    except Exception as e:
        os.system("systemctl start nginx")
        return False, str(e)

def generate_self_signed_cert(domain_or_ip="127.0.0.1"):
    """Generates a self-signed certificate for internal tunnels (e.g. Backhaul)."""
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)
    
    key_file = f"{CERT_DIR}/server.key"
    crt_file = f"{CERT_DIR}/server.crt"
    
    # If they exist, verify they are not empty
    if os.path.exists(crt_file) and os.path.exists(key_file):
        if os.path.getsize(crt_file) > 0:
            return True, crt_file, key_file

    try:
        cmd = f"openssl req -x509 -newkey rsa:2048 -keyout {key_file} -out {crt_file} -days 3650 -nodes -subj '/CN={domain_or_ip}'"
        subprocess.run(cmd, shell=True, check=True)
        return True, crt_file, key_file
    except Exception as e:
        return False, str(e), None

def setup_secure_panel_nginx(domain, secret_path):
    """
    Configures Nginx to listen ONLY on the custom panel port (e.g., 2096).
    Ports 80 and 443 are left strictly alone for tunnels.
    """
    try:
        config = load_config()
        panel_port = config.get('panel_port', DEFAULT_PANEL_PORT)

        if not os.path.exists("/usr/sbin/nginx"):
            os.system("apt-get update && apt-get install -y nginx")

        os.system(f"ufw allow {panel_port}/tcp")

        # 1. Ensure SSL
        if not os.path.exists(f"/etc/letsencrypt/live/{domain}/fullchain.pem"):
            res, msg = generate_letsencrypt_cert(domain)
            if not res: return False, msg

        # 2. Nginx Config (Panel Port Only)
        nginx_conf = f"""
server {{
    listen {panel_port} ssl http2;
    server_name {domain};
    
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
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
"""
        with open(f"{NGINX_SITE_PATH}/{domain}", "w") as f:
            f.write(nginx_conf)
            
        os.system(f"ln -sf {NGINX_SITE_PATH}/{domain} {NGINX_ENABLED_PATH}/")
        
        if os.path.exists(f"{NGINX_ENABLED_PATH}/default"):
            os.remove(f"{NGINX_ENABLED_PATH}/default")
            
        os.system("systemctl restart nginx")
        
        save_config('panel_domain', domain)
        save_config('panel_port', panel_port)
        
        return True, f"Panel secured on port {panel_port}"
    except Exception as e:
        return False, str(e)

def set_root_tunnel(target_port):
    """
    Legacy support: This function is kept to prevent ImportErrors in routes/tunnels.py.
    Since we are now using Port 443 for direct tunnels (Hysteria), using this might conflict.
    However, it must exist for the code to run.
    """
    return False, "This feature is disabled to keep Port 443 free for Hysteria."