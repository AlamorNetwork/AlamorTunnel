import os
import secrets
import subprocess
from core.ssh_manager import run_remote_command

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel/bin"
LOCAL_REPO = "http://files.irplatforme.ir/files/hysteria.tar.gz"
REMOTE_REPO = "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64"

def check_binary(binary_name):
    file_path = f"{INSTALL_DIR}/{binary_name}"
    if os.path.exists(file_path): return True
    try:
        if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)
        # اضافه شدن -k
        subprocess.run(f"curl -k -L -o {file_path}.tar.gz {LOCAL_REPO}", shell=True, check=True)
        subprocess.run(f"tar -xzf {file_path}.tar.gz -C {INSTALL_DIR}", shell=True, check=True)
        subprocess.run(f"chmod +x {file_path}", shell=True, check=True)
        if os.path.exists(f"{file_path}.tar.gz"): os.remove(f"{file_path}.tar.gz")
        return True
    except: return False

def generate_pass():
    return secrets.token_hex(8)

def install_hysteria_server_remote(ssh_ip, config):
    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/hysteria ]; then
        curl -L -o {INSTALL_DIR}/hysteria {REMOTE_REPO}
        chmod +x {INSTALL_DIR}/hysteria
    fi
    
    if [ ! -f {INSTALL_DIR}/server.crt ]; then
        openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
            -subj "/CN=bing.com" -keyout {INSTALL_DIR}/server.key -out {INSTALL_DIR}/server.crt
    fi

    cat > {INSTALL_DIR}/hysteria_config.yaml <<EOL
listen: :{config['tunnel_port']}
tls:
  cert: {INSTALL_DIR}/server.crt
  key: {INSTALL_DIR}/server.key
auth:
  type: password
  password: "{config['password']}"
obfs:
  type: salamander
  salamander:
    password: "{config['obfs_pass']}"
EOL

    cat > /etc/systemd/system/hysteria-server.service <<EOL
[Unit]
Description=Hysteria Server
After=network.target
[Service]
ExecStart={INSTALL_DIR}/hysteria server -c {INSTALL_DIR}/hysteria_config.yaml
Restart=always
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
EOL

    ufw allow {config['tunnel_port']}/udp
    ufw allow {config['tunnel_port']}/tcp
    systemctl daemon-reload && systemctl enable hysteria-server && systemctl restart hysteria-server
    """
    return run_remote_command(ssh_ip, remote_script)

def install_hysteria_client_local(remote_ip, config):
    if not check_binary("hysteria"):
        raise Exception("Hysteria binary missing.")

    rules = ""
    for p in config['ports']:
        rules += f"\n  - listen: :{p}\n    remote: 127.0.0.1:{p}"

    config_content = f"""
server: {remote_ip}:{config['tunnel_port']}
auth: "{config['password']}"
tls:
  insecure: true
  sni: bing.com
obfs:
  type: salamander
  salamander:
    password: "{config['obfs_pass']}"
bandwidth:
  up: {config['up_mbps']} mbps
  down: {config['down_mbps']} mbps
tcpForwarding:{rules}
udpForwarding:{rules}
"""
    with open(f"{INSTALL_DIR}/hysteria_client.yaml", "w") as f:
        f.write(config_content)

    svc = f"""
[Unit]
Description=Hysteria Client
After=network.target
[Service]
ExecStart={INSTALL_DIR}/hysteria client -c {INSTALL_DIR}/hysteria_client.yaml
Restart=always
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/hysteria-client.service", "w") as f:
        f.write(svc)
    os.system("systemctl daemon-reload && systemctl enable hysteria-client && systemctl restart hysteria-client")
    return True