import os
import secrets
import subprocess
from core.ssh_manager import run_remote_command
from core.ssl_manager import generate_self_signed_cert

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel/bin"
LOCAL_REPO = "https://files.irplatforme.ir/files/backhaul.tar.gz"
REMOTE_REPO = "https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz"

def check_binary(binary_name):
    """دانلود هوشمند فایل اجرایی در سرور ایران"""
    file_path = f"{INSTALL_DIR}/{binary_name}"
    
    if os.path.exists(file_path): 
        return True
    
    print(f"[Manager] Downloading {binary_name} from Private Repo...")
    try:
        if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)
        
        # اضافه شدن -k برای نادیده گرفتن خطای SSL
        cmd = f"curl -k -L -o {file_path}.tar.gz {LOCAL_REPO}"
        subprocess.run(cmd, shell=True, check=True)
        
        subprocess.run(f"tar -xzf {file_path}.tar.gz -C {INSTALL_DIR}", shell=True, check=True)
        subprocess.run(f"chmod +x {file_path}", shell=True, check=True)
        
        if os.path.exists(f"{file_path}.tar.gz"): os.remove(f"{file_path}.tar.gz")
        return True
    except Exception as e:
        print(f"[Manager] Error downloading {binary_name}: {e}")
        return False

def generate_token():
    return secrets.token_hex(16)

def install_local_backhaul(config):
    if not check_binary("backhaul"):
        raise Exception("Failed to install Backhaul locally.")

    tls_lines = ""
    if config['transport'] in ["wss", "wssmux"]:
        generate_self_signed_cert("127.0.0.1")
        tls_lines = f'tls_cert = "/root/certs/server.crt"\ntls_key = "/root/certs/server.key"'

    port_rules = config.get('port_rules', [])
    formatted_ports = ",\n    ".join([f'"{p.strip()}"' for p in port_rules if p.strip()])

    config_content = f"""
[server]
bind_addr = "0.0.0.0:{config['tunnel_port']}"
transport = "{config['transport']}"
accept_udp = {str(config.get('accept_udp', False)).lower()}
token = "{config['token']}"
keepalive_period = {config.get('keepalive_period', 75)}
nodelay = {str(config.get('nodelay', False)).lower()}
channel_size = {config.get('channel_size', 2048)}
heartbeat = {config.get('heartbeat', 40)}
mux_con = {config.get('mux_con', 8)}
mux_version = {config.get('mux_version', 1)}
mux_framesize = {config.get('mux_framesize', 32768)}
mux_recievebuffer = {config.get('mux_recievebuffer', 4194304)}
mux_streambuffer = {config.get('mux_streambuffer', 65536)}
sniffer = {str(config.get('sniffer', False)).lower()}
web_port = {config.get('web_port', 2060)}
sniffer_log = "/root/log.json"
log_level = "{config.get('log_level', 'info')}"
skip_optz = {str(config.get('skip_optz', True)).lower()}
mss = {config.get('mss', 1360)}
so_rcvbuf = {config.get('so_rcvbuf', 4194304)}
so_sndbuf = {config.get('so_sndbuf', 1048576)}
{tls_lines}

ports = [
    {formatted_ports}
]
"""
    with open(f"{INSTALL_DIR}/backhaul_config.toml", "w") as f:
        f.write(config_content)

    service_content = f"""
[Unit]
Description=Backhaul Server
After=network.target
[Service]
Type=simple
ExecStart={INSTALL_DIR}/backhaul -c {INSTALL_DIR}/backhaul_config.toml
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/backhaul.service", "w") as f:
        f.write(service_content)

    os.system(f"ufw allow {config['tunnel_port']}/tcp")
    os.system(f"ufw allow {config['tunnel_port']}/udp")
    os.system("systemctl daemon-reload && systemctl enable backhaul && systemctl restart backhaul")
    return True

def install_remote_backhaul(ssh_target_ip, iran_connect_ip, config):
    clean_ip = iran_connect_ip.strip()
    edge_line = f'edge_ip = "{config["edge_ip"]}"' if config.get('edge_ip') else ""
    
    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/backhaul ]; then
        echo "Downloading Backhaul from GitHub..."
        curl -L --max-time 60 -o {INSTALL_DIR}/backhaul.tar.gz {REMOTE_REPO}
        tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/backhaul
    fi
    
    cat > {INSTALL_DIR}/client_config.toml <<EOL
[client]
remote_addr = "{clean_ip}:{config['tunnel_port']}"
{edge_line}
transport = "{config['transport']}"
token = "{config['token']}"
connection_pool = {config.get('connection_pool', 8)}
aggressive_pool = {str(config.get('aggressive_pool', False)).lower()}
keepalive_period = {config.get('keepalive_period', 75)}
nodelay = {str(config.get('nodelay', False)).lower()}
retry_interval = {config.get('retry_interval', 3)}
dial_timeout = {config.get('dial_timeout', 10)}
mux_version = {config.get('mux_version', 1)}
mux_framesize = {config.get('mux_framesize', 32768)}
mux_recievebuffer = {config.get('mux_recievebuffer', 4194304)}
mux_streambuffer = {config.get('mux_streambuffer', 65536)}
sniffer = {str(config.get('sniffer', False)).lower()}
web_port = {config.get('web_port', 2060)}
sniffer_log = "/root/backhaul_client_log.json"
log_level = "{config.get('log_level', 'info')}"
skip_optz = {str(config.get('skip_optz', True)).lower()}
mss = {config.get('mss', 1360)}
so_rcvbuf = {config.get('so_rcvbuf', 4194304)}
so_sndbuf = {config.get('so_sndbuf', 1048576)}
EOL

    cat > /etc/systemd/system/backhaul.service <<EOL
[Unit]
Description=Backhaul Client
After=network.target
[Service]
Type=simple
ExecStart={INSTALL_DIR}/backhaul -c {INSTALL_DIR}/client_config.toml
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
EOL

    systemctl daemon-reload && systemctl enable backhaul && systemctl restart backhaul
    """
    return run_remote_command(ssh_target_ip, remote_script)

def stop_and_delete_backhaul():
    os.system("systemctl stop backhaul && systemctl disable backhaul")
    return True