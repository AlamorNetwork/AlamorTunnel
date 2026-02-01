import os
import subprocess
from core.ssh_manager import run_remote_command

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel/bin"
REPO_URL = "https://files.irplatforme.ir/files"

def check_binary(binary_name):
    # چک کردن هر دو فایل کلاینت و سرور
    client_path = f"{INSTALL_DIR}/slipstream-client"
    server_path = f"{INSTALL_DIR}/slipstream-server"
    
    if os.path.exists(client_path) and os.path.exists(server_path): return True
    
    try:
        if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)
        # دانلود پک کامل اسلیپ‌استریم
        subprocess.run(f"curl -L -o {INSTALL_DIR}/slipstream.tar.gz {REPO_URL}/slipstream.tar.gz", shell=True, check=True)
        subprocess.run(f"tar -xzf {INSTALL_DIR}/slipstream.tar.gz -C {INSTALL_DIR}", shell=True, check=True)
        subprocess.run(f"chmod +x {client_path}", shell=True, check=True)
        subprocess.run(f"chmod +x {server_path}", shell=True, check=True)
        if os.path.exists(f"{INSTALL_DIR}/slipstream.tar.gz"): os.remove(f"{INSTALL_DIR}/slipstream.tar.gz")
        return True
    except: return False

def install_slipstream_server_remote_gen(ssh_ip, config):
    # اسکریپت ریموت برای سرور خارج (دانلود باینری)
    script = f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/slipstream-server ]; then
        curl -L -o {INSTALL_DIR}/slipstream.tar.gz {REPO_URL}/slipstream.tar.gz
        tar -xzf {INSTALL_DIR}/slipstream.tar.gz -C {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/slipstream-server
    fi
    
    cd {INSTALL_DIR}
    if [ ! -f cert.pem ]; then
        openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 3650 -subj "/CN={config['domain']}"
    fi
    
    ufw allow {config['tunnel_port']}/udp
    
    cat > /etc/systemd/system/slipstream-server.service <<EOL
[Unit]
Description=Slipstream Server
After=network.target
[Service]
WorkingDirectory={INSTALL_DIR}
ExecStart={INSTALL_DIR}/slipstream-server \\
  --dns-listen-port {config['tunnel_port']} \\
  --target-address 127.0.0.1:{config['dest_port']} \\
  --domain {config['domain']} \\
  --cert ./cert.pem \\
  --key ./key.pem \\
  --reset-seed ./reset-seed
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload && systemctl enable slipstream-server && systemctl restart slipstream-server
    """
    
    success, out = run_remote_command(ssh_ip, script)
    yield "Remote Installation Complete." if success else f"Remote Error: {out}"

def install_slipstream_client_local_gen(remote_ip, config):
    if not check_binary("slipstream-client"):
        raise Exception("Slipstream binaries missing locally.")

    svc = f"""
[Unit]
Description=Slipstream Client
After=network.target
[Service]
WorkingDirectory={INSTALL_DIR}
ExecStart={INSTALL_DIR}/slipstream-client \\
  --tcp-listen-port {config['client_port']} \\
  --resolver {remote_ip}:{config['tunnel_port']} \\
  --domain {config['domain']}
Restart=always
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/slipstream-client.service", "w") as f:
        f.write(svc)
    
    os.system("systemctl daemon-reload && systemctl enable slipstream-client && systemctl restart slipstream-client")
    yield "Local Service Started."