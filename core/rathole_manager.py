import os
import secrets
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/rathole-core"
# هر وقت سرور ایران زدی، این لینک رو عوض کن
MIRROR_URL = "https://github.com/Musixal/rathole-tunnel/raw/main/core/rathole.zip"

def generate_token():
    return secrets.token_hex(16)

def install_rathole_core():
    if not os.path.exists(f"{INSTALL_DIR}/rathole"):
        print("[+] Installing Rathole Core...")
        cmds = [
            "apt-get update && apt-get install -y unzip",
            f"mkdir -p {INSTALL_DIR}",
            f"curl -L -o {INSTALL_DIR}/rathole.zip {MIRROR_URL}",
            f"unzip -o {INSTALL_DIR}/rathole.zip -d {INSTALL_DIR}",
            f"chmod +x {INSTALL_DIR}/rathole",
            f"rm {INSTALL_DIR}/rathole.zip"
        ]
        for cmd in cmds:
            os.system(cmd)
    return True

def install_local_rathole(config_data):
    install_rathole_core()
    
    tunnel_port = config_data['tunnel_port']
    print(f"[+] Configuring Local Rathole (Iran) on port {tunnel_port}...")

    bind_ip = "[::]" if config_data['ipv6'] else "0.0.0.0"
    
    transport_block = f"""
[server.transport]
type = "{config_data['transport']}"
"""
    if config_data['transport'] == 'tcp':
        transport_block += f"""
[server.transport.tcp]
nodelay = {str(config_data['nodelay']).lower()}
"""

    hb_interval = 30 if config_data['heartbeat'] else 0
    
    config_content = f"""
[server]
bind_addr = "{bind_ip}:{tunnel_port}"
default_token = "{config_data['token']}"
heartbeat_interval = {hb_interval}

{transport_block}
"""

    for port in config_data['ports']:
        config_content += f"""
[server.services.{port}]
type = "{config_data['transport']}"
bind_addr = "{bind_ip}:{port}"
"""

    config_path = f"{INSTALL_DIR}/iran{tunnel_port}.toml"
    with open(config_path, "w") as f:
        f.write(config_content)

    service_name = f"rathole-iran{tunnel_port}"
    service_content = f"""
[Unit]
Description=Rathole Iran Port {tunnel_port}
After=network.target

[Service]
Type=simple
ExecStart={INSTALL_DIR}/rathole {config_path}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    with open(f"/etc/systemd/system/{service_name}.service", "w") as f:
        f.write(service_content)

    os.system(f"systemctl daemon-reload && systemctl enable {service_name} && systemctl restart {service_name}")
    return True

def install_remote_rathole(ssh_target_ip, iran_ip, config_data):
    tunnel_port = config_data['tunnel_port']
    print(f"[+] Configuring Remote Rathole on {ssh_target_ip}...")
    
    remote_addr = f"{iran_ip}:{tunnel_port}"
    if ":" in iran_ip and not iran_ip.startswith("["):
        remote_addr = f"[{iran_ip}]:{tunnel_port}"

    hb_timeout = 40 if config_data['heartbeat'] else 0
    local_bind = "[::]" if config_data['ipv6'] else "0.0.0.0"
    
    services_block = ""
    for port in config_data['ports']:
        services_block += f"""
[client.services.{port}]
type = "{config_data['transport']}"
local_addr = "{local_bind}:{port}"
"""

    remote_script = f"""
    apt-get update && apt-get install -y unzip
    mkdir -p {INSTALL_DIR}
    
    if [ ! -f {INSTALL_DIR}/rathole ]; then
        curl -L -o {INSTALL_DIR}/rathole.zip {MIRROR_URL}
        unzip -o {INSTALL_DIR}/rathole.zip -d {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/rathole
        rm {INSTALL_DIR}/rathole.zip
    fi

    cat > {INSTALL_DIR}/kharej{tunnel_port}.toml <<EOL
[client]
remote_addr = "{remote_addr}"
default_token = "{config_data['token']}"
heartbeat_timeout = {hb_timeout}
retry_interval = 1

[client.transport]
type = "{config_data['transport']}"

[client.transport.tcp]
nodelay = {str(config_data['nodelay']).lower()}

{services_block}
EOL

    cat > /etc/systemd/system/rathole-kharej{tunnel_port}.service <<EOL
[Unit]
Description=Rathole Kharej Port {tunnel_port}
After=network.target

[Service]
Type=simple
ExecStart={INSTALL_DIR}/rathole {INSTALL_DIR}/kharej{tunnel_port}.toml
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOL

    systemctl daemon-reload
    systemctl enable rathole-kharej{tunnel_port}
    systemctl restart rathole-kharej{tunnel_port}
    """
    
    success, output = run_remote_command(ssh_target_ip, remote_script)
    return success, output