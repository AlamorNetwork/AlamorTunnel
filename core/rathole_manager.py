import os
import secrets
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/rathole-core"
BIN_URL = "https://github.com/Musixal/rathole-tunnel/raw/main/core/rathole.zip"

def install_rathole_core():
    if not os.path.exists(f"{INSTALL_DIR}/rathole"):
        os.system("apt-get install -y unzip")
        os.system(f"mkdir -p {INSTALL_DIR}")
        os.system(f"curl -L -o {INSTALL_DIR}/rathole.zip {BIN_URL}")
        os.system(f"unzip -o {INSTALL_DIR}/rathole.zip -d {INSTALL_DIR}")
        os.system(f"chmod +x {INSTALL_DIR}/rathole")
        os.system(f"rm {INSTALL_DIR}/rathole.zip")
    return True

def install_local_rathole(config_data):
    install_rathole_core()
    port = config_data['tunnel_port']
    bind_ip = "[::]" if config_data['ipv6'] else "0.0.0.0"
    
    transport_block = f'[server.transport]\ntype = "{config_data["transport"]}"'
    if config_data['transport'] == 'tcp':
        transport_block += f'\n[server.transport.tcp]\nnodelay = {str(config_data["nodelay"]).lower()}'

    services = ""
    for p in config_data['ports']:
        services += f'\n[server.services.{p}]\ntype = "{config_data["transport"]}"\nbind_addr = "{bind_ip}:{p}"\n'

    config_content = f"""
[server]
bind_addr = "{bind_ip}:{port}"
default_token = "{config_data['token']}"
{transport_block}
{services}
"""
    with open(f"{INSTALL_DIR}/iran{port}.toml", "w") as f:
        f.write(config_content)

    svc_name = f"rathole-iran{port}"
    svc_content = f"""
[Unit]
Description=Rathole Iran {port}
After=network.target
[Service]
ExecStart={INSTALL_DIR}/rathole {INSTALL_DIR}/iran{port}.toml
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
    
    services = ""
    for p in config_data['ports']:
        services += f'\n[client.services.{p}]\ntype = "{config_data["transport"]}"\nlocal_addr = "0.0.0.0:{p}"\n'

    remote_script = f"""
    apt-get install -y unzip
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/rathole ]; then
        curl -L -o {INSTALL_DIR}/rathole.zip {BIN_URL}
        unzip -o {INSTALL_DIR}/rathole.zip -d {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/rathole
    fi

    cat > {INSTALL_DIR}/kharej{port}.toml <<EOL
[client]
remote_addr = "{remote_addr}"
default_token = "{config_data['token']}"
retry_interval = 1
[client.transport]
type = "{config_data['transport']}"
[client.transport.tcp]
nodelay = {str(config_data['nodelay']).lower()}
{services}
EOL

    cat > /etc/systemd/system/rathole-kharej{port}.service <<EOL
[Unit]
Description=Rathole Kharej {port}
After=network.target
[Service]
ExecStart={INSTALL_DIR}/rathole {INSTALL_DIR}/kharej{port}.toml
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload
    systemctl enable rathole-kharej{port}
    systemctl restart rathole-kharej{port}
    """
    return run_remote_command(ssh_ip, remote_script)