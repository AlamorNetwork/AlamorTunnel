import os
import secrets
import subprocess
import hashlib
from core.ssh_manager import run_remote_command

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_DIR = os.path.join(BASE_DIR, "bin")

LOCAL_REPO = "http://files.irplatforme.ir/files/hysteria.tar.gz"
REMOTE_REPO = "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64"

def check_binary(binary_name):
    """دانلود هوشمند با بررسی سلامت فایل و فال‌بک"""
    file_path = os.path.join(INSTALL_DIR, binary_name)
    
    if os.path.exists(file_path) and os.path.getsize(file_path) > 2 * 1024 * 1024:
        return True
    
    if os.path.exists(file_path): os.remove(file_path)
    if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)

    try:
        subprocess.run(f"curl -k -L -f --max-time 15 -o {file_path}.tar.gz {LOCAL_REPO}", shell=True, check=True)
        subprocess.run(f"tar -xzf {file_path}.tar.gz -C {INSTALL_DIR}", shell=True, check=True)
        subprocess.run(f"chmod +x {file_path}", shell=True, check=True)
        if os.path.exists(f"{file_path}.tar.gz"): os.remove(f"{file_path}.tar.gz")
        return True
    except:
        pass # Try remote if local fails
    
    try:
        subprocess.run(f"curl -L -f -o {file_path} {REMOTE_REPO}", shell=True, check=True)
        subprocess.run(f"chmod +x {file_path}", shell=True, check=True)
        return True
    except Exception as e:
        print(f"Failed to download Hysteria: {e}")
        return False

def generate_pass():
    return secrets.token_hex(16)

def install_hysteria_server_remote(ssh_ip, config):
    # استخراج مقادیر از دیکشنری کانفیگ (با مقادیر پیش‌فرض محض اطمینان)
    listen_port = config.get('tunnel_port', '443')
    hop_start = config.get('hop_start', '20000')
    hop_end = config.get('hop_end', '50000')
    masq_url = config.get('masq_url', 'https://www.bing.com')
    up_mbps = config.get('up_mbps', '1000')
    down_mbps = config.get('down_mbps', '1000')
    obfs_pass = config.get('obfs_pass', 'secret')
    password = config.get('password', 'secret')

    remote_script = f"""
    # [cite_start]1. System Optimization [cite: 326]
    sysctl -w net.core.rmem_max=16777216
    sysctl -w net.core.wmem_max=16777216
    
    # اطمینان از پاک بودن قوانین قبلی iptables برای جلوگیری از تداخل
    apt-get install -y iptables iptables-persistent
    iptables -t nat -D PREROUTING -p udp --dport {hop_start}:{hop_end} -j REDIRECT --to-ports {listen_port} 2>/dev/null || true

    # 2. Setup Env
    mkdir -p /root/alamor/bin
    cd /root/alamor/bin
    
    if [ ! -f hysteria ]; then
        curl -L -o hysteria {REMOTE_REPO}
        chmod +x hysteria
    fi
    
    # 3. Cert Generation
    if [ ! -f server.crt ]; then
        openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
            -subj "/CN=www.bing.com" -keyout server.key -out server.crt
    fi

    # 4. Config File Generation
    cat > config.yaml <<EOL
listen: :{listen_port}

tls:
  cert: /root/alamor/bin/server.crt
  key: /root/alamor/bin/server.key

auth:
  type: password
  password: "{password}"

obfs:
  type: salamander
  salamander:
    password: "{obfs_pass}"

bandwidth:
  up: {up_mbps} mbps
  down: {down_mbps} mbps

ignoreClientBandwidth: false

masquerade:
  type: proxy
  proxy:
    url: {masq_url}
    rewriteHost: true
    insecure: true
EOL

    # [cite_start]5. Port Hopping Rules [cite: 308]
    iptables -t nat -A PREROUTING -p udp --dport {hop_start}:{hop_end} -j REDIRECT --to-ports {listen_port}
    netfilter-persistent save

    # 6. Service Definition
    cat > /etc/systemd/system/hysteria-server.service <<EOL
[Unit]
Description=Hysteria Server
After=network.target

[Service]
ExecStart=/root/alamor/bin/hysteria server -c /root/alamor/bin/config.yaml
Restart=always
LimitNOFILE=1048576
CPUSchedulingPolicy=rr
CPUSchedulingPriority=50

[Install]
WantedBy=multi-user.target
EOL

    ufw allow {listen_port}/udp
    ufw allow {listen_port}/tcp
    ufw allow {hop_start}:{hop_end}/udp

    systemctl daemon-reload && systemctl enable hysteria-server && systemctl restart hysteria-server
    """
    return run_remote_command(ssh_ip, remote_script)

def install_hysteria_client_local(remote_ip, config):
    if not check_binary("hysteria"):
        raise Exception("Hysteria binary download failed locally.")

    rules = ""
    for p in config['ports']:
        rules += f"\n  - listen: :{p}\n    remote: 127.0.0.1:{p}"

    # [cite_start]استفاده از بازه پورت برای آدرس سرور (Client Port Hopping) [cite: 303]
    hop_start = config.get('hop_start', '20000')
    hop_end = config.get('hop_end', '50000')
    server_address = f"{remote_ip}:{hop_start}-{hop_end}"
    
    config_content = f"""
server: {server_address}

auth: "{config['password']}"

tls:
  insecure: true
  sni: www.bing.com

obfs:
  type: salamander
  salamander:
    password: "{config['obfs_pass']}"

bandwidth:
  up: {config.get('up_mbps', '1000')} mbps
  down: {config.get('down_mbps', '1000')} mbps

fastOpen: true

transport:
  type: udp
  udp:
    hopInterval: {config.get('hop_interval', '30s')}

tcpForwarding:{rules}
udpForwarding:{rules}
"""
    client_config_path = os.path.join(INSTALL_DIR, "hysteria_client.yaml")
    with open(client_config_path, "w") as f:
        f.write(config_content)

    hysteria_bin = os.path.join(INSTALL_DIR, "hysteria")
    
    svc = f"""
[Unit]
Description=Hysteria Client
After=network.target
[Service]
ExecStart={hysteria_bin} client -c {client_config_path}
Restart=always
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/hysteria-client.service", "w") as f:
        f.write(svc)
        
    os.system("systemctl daemon-reload && systemctl enable hysteria-client && systemctl restart hysteria-client")
    return True