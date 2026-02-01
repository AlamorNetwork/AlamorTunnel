import os
import subprocess
from core.ssh_manager import run_remote_command

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel/bin"
LOCAL_REPO = "http://files.irplatforme.ir/files/gost.tar.gz"
REMOTE_REPO = "https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz"

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

def install_gost_server_remote(ssh_ip, config):
    script = f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/gost ]; then
        curl -L -o {INSTALL_DIR}/gost.gz {REMOTE_REPO}
        gzip -d -f {INSTALL_DIR}/gost.gz
        chmod +x {INSTALL_DIR}/gost
    fi
    
    cd {INSTALL_DIR}
    if [ ! -f cert.pem ]; then
        openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj "/CN=bing.com" -keyout key.pem -out cert.pem
    fi
    
    ufw allow {config['tunnel_port']}/tcp
    
    cat > /etc/systemd/system/gost-server.service <<EOL
[Unit]
Description=GOST Server
After=network.target
[Service]
ExecStart={INSTALL_DIR}/gost -L=relay+tls://:{config['tunnel_port']}?cert={INSTALL_DIR}/cert.pem&key={INSTALL_DIR}/key.pem
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload && systemctl enable gost-server && systemctl restart gost-server
    """
    return run_remote_command(ssh_ip, script)

def install_gost_client_local(remote_ip, config):
    if not check_binary("gost"):
        raise Exception("Gost binary missing locally.")

    cmd = f"{INSTALL_DIR}/gost -L=tcp://:{config['client_port']}/127.0.0.1:{config['dest_port']} -F=relay+tls://{remote_ip}:{config['tunnel_port']}?secure=true"
    svc = f"""
[Unit]
Description=GOST Client
After=network.target
[Service]
ExecStart={cmd}
Restart=always
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/gost-client.service", "w") as f:
        f.write(svc)
    os.system("systemctl daemon-reload && systemctl enable gost-client && systemctl restart gost-client")
    return True