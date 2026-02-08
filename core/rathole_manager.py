import os
import subprocess
import logging
# استفاده از کلاس SSHManager بجای تابع تکی
from core.ssh_manager import SSHManager

logger = logging.getLogger("RatholeManager")
INSTALL_DIR = "/root/AlamorTunnel/bin"
REMOTE_REPO = "https://github.com/rapiz1/rathole/releases/latest/download/rathole-x86_64-unknown-linux-gnu.zip"

def check_binary(binary_name):
    file_path = f"{INSTALL_DIR}/{binary_name}"
    if os.path.exists(file_path): return True
    try:
        if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)
        subprocess.run(f"curl -k -L -o {file_path}.zip {REMOTE_REPO}", shell=True, check=True)
        subprocess.run(f"unzip -o {file_path}.zip -d {INSTALL_DIR}", shell=True, check=True)
        subprocess.run(f"chmod +x {file_path}", shell=True, check=True)
        return True
    except Exception as e:
        logger.error(f"Binary Check Failed: {e}")
        return False

def install_local_rathole(config_data):
    if not check_binary("rathole"):
        raise Exception("Rathole binary missing locally.")
        
    port = config_data['tunnel_port']
    bind_ip = "[::]" if config_data.get('ipv6') else "0.0.0.0"
    
    transport_block = f'[server.transport]\ntype = "{config_data.get("transport", "tcp")}"'
    if config_data.get('transport') == 'tcp':
        transport_block += f'\n[server.transport.tcp]\nnodelay = {str(config_data.get("nodelay", True)).lower()}'

    services = ""
    for p in config_data['ports']:
        services += f'\n[server.services.{p}]\ntype = "{config_data.get("transport", "tcp")}"\nbind_addr = "{bind_ip}:{p}"\n'

    config_content = f"""
[server]
bind_addr = "{bind_ip}:{port}"
default_token = "{config_data['token']}"
{transport_block}
{services}
"""
    with open(f"{INSTALL_DIR}/rathole_iran{port}.toml", "w") as f:
        f.write(config_content)

    svc_name = f"rathole-iran{port}"
    svc_content = f"""[Unit]
Description=Rathole Iran {port}
After=network.target
[Service]
ExecStart={INSTALL_DIR}/rathole {INSTALL_DIR}/rathole_iran{port}.toml
Restart=always
[Install]
WantedBy=multi-user.target
"""
    with open(f"/etc/systemd/system/{svc_name}.service", "w") as f:
        f.write(svc_content)
    os.system(f"systemctl daemon-reload && systemctl enable {svc_name} && systemctl restart {svc_name}")
    return True

def install_remote_rathole(ssh_ip, iran_ip, config_data):
    port = config_data['tunnel_port']
    remote_addr = f"[{iran_ip}]:{port}" if ":" in iran_ip and not iran_ip.startswith("[") else f"{iran_ip}:{port}"
    
    # ساخت سرویس‌ها
    services = ""
    for p in config_data['ports']:
        services += f'\n[client.services.{p}]\ntype = "{config_data.get("transport", "tcp")}"\nlocal_addr = "0.0.0.0:{p}"\n'

    # دریافت اطلاعات اتصال SSH از کانفیگ
    ssh_user = config_data.get('ssh_user', 'root')
    ssh_pass = config_data.get('ssh_pass')
    ssh_key = config_data.get('ssh_key')
    ssh_port = int(config_data.get('ssh_port', 22))

    remote_script = f"""
    export DEBIAN_FRONTEND=noninteractive
    apt-get update && apt-get install -y unzip curl
    mkdir -p /root/alamor/bin
    if [ ! -f /root/alamor/bin/rathole ]; then
        curl -L -k -o /tmp/rathole.zip {REMOTE_REPO}
        unzip -o /tmp/rathole.zip -d /root/alamor/bin/
        chmod +x /root/alamor/bin/rathole
    fi

    cat > /root/alamor/bin/rathole_kharej{port}.toml <<EOL
[client]
remote_addr = "{remote_addr}"
default_token = "{config_data['token']}"
retry_interval = 1
[client.transport]
type = "{config_data.get('transport', 'tcp')}"
[client.transport.tcp]
nodelay = {str(config_data.get('nodelay', True)).lower()}
{services}
EOL

    cat > /etc/systemd/system/rathole-kharej{port}.service <<EOL
[Unit]
Description=Rathole Kharej {port}
After=network.target
[Service]
ExecStart=/root/alamor/bin/rathole /root/alamor/bin/rathole_kharej{port}.toml
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload && systemctl enable rathole-kharej{port} && systemctl restart rathole-kharej{port}
    """
    
    # استفاده صحیح از SSHManager
    ssh = SSHManager()
    return ssh.run_remote_command(ssh_ip, ssh_user, ssh_pass, remote_script, ssh_port, ssh_key)