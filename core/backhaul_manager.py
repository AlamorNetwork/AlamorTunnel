import os
import secrets
from core.ssh_manager import run_remote_command
from core.ssl_manager import generate_self_signed_cert

INSTALL_DIR = "/root/backhaul"
BIN_URL = "https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz"

def generate_token():
    return secrets.token_hex(16)

def install_local_backhaul(config_data):
    """نصب روی سرور ایران (سرور تانل)"""
    if not os.path.exists(f"{INSTALL_DIR}/backhaul"):
        os.system(f"mkdir -p {INSTALL_DIR}")
        os.system(f"curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}")
        os.system(f"tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}")
        os.system(f"chmod +x {INSTALL_DIR}/backhaul")

    # تولید SSL برای متدهای WSS
    if config_data['transport'] in ["wss", "wssmux"]:
        generate_self_signed_cert(domain_or_ip="127.0.0.1")

    port_rules = config_data.get('port_rules', [])
    formatted_ports = ",\n".join([f'"{p.strip()}"' for p in port_rules if p.strip()])

    config_content = f"""
[server]
bind_addr = "0.0.0.0:{config_data['tunnel_port']}"
transport = "{config_data['transport']}"
accept_udp = {str(config_data.get('accept_udp', False)).lower()}
token = "{config_data['token']}"
keepalive_period = {config_data.get('keepalive_period', 75)}
nodelay = {str(config_data.get('nodelay', False)).lower()}
channel_size = {config_data.get('channel_size', 2048)}
sniffer = {str(config_data.get('sniffer', False)).lower()}
web_port = 2060
log_level = "info"
ports = [
{formatted_ports}
]
"""
    with open(f"{INSTALL_DIR}/config.toml", "w") as f:
        f.write(config_content)

    service_content = f"""
[Unit]
Description=Backhaul Server (Alamor)
After=network.target
[Service]
Type=simple
ExecStart={INSTALL_DIR}/backhaul -c {INSTALL_DIR}/config.toml
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/backhaul.service", "w") as f:
        f.write(service_content)

    os.system("systemctl daemon-reload && systemctl enable backhaul && systemctl restart backhaul")
    return True

def install_remote_backhaul(ssh_target_ip, iran_connect_ip, config_data):
    """نصب روی سرور خارج (کلاینت تانل)"""
    clean_ip = iran_connect_ip.strip()
    edge_line = f'edge_ip = "{config_data["edge_ip"]}"' if config_data.get('edge_ip') else ""
    
    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/backhaul ]; then
        curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}
        tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/backhaul
    fi
    
    cat > {INSTALL_DIR}/config.toml <<EOL
[client]
remote_addr = "{clean_ip}:{config_data['tunnel_port']}"
{edge_line}
transport = "{config_data['transport']}"
token = "{config_data['token']}"
connection_pool = 8
keepalive_period = {config_data.get('keepalive_period', 75)}
nodelay = {str(config_data.get('nodelay', False)).lower()}
sniffer = {str(config_data.get('sniffer', False)).lower()}
log_level = "info"
EOL

    cat > /etc/systemd/system/backhaul.service <<EOL
[Unit]
Description=Backhaul Client (Alamor)
After=network.target
[Service]
Type=simple
ExecStart={INSTALL_DIR}/backhaul -c {INSTALL_DIR}/config.toml
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
EOL

    systemctl daemon-reload
    systemctl enable backhaul
    systemctl restart backhaul
    """
    return run_remote_command(ssh_target_ip, remote_script)

def stop_and_delete_backhaul():
    os.system("systemctl stop backhaul && systemctl disable backhaul")
    os.system(f"rm -f {INSTALL_DIR}/config.toml")
    return True