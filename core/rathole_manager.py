import os
import subprocess
from core.ssh_manager import run_remote_command

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel/bin"
REPO_URL = "https://files.irplatforme.ir/files"

def check_binary(binary_name):
    file_path = f"{INSTALL_DIR}/{binary_name}"
    if os.path.exists(file_path): return True
    try:
        if not os.path.exists(INSTALL_DIR): os.makedirs(INSTALL_DIR)
        subprocess.run(f"curl -L -o {file_path}.tar.gz {REPO_URL}/{binary_name}.tar.gz", shell=True, check=True)
        subprocess.run(f"tar -xzf {file_path}.tar.gz -C {INSTALL_DIR}", shell=True, check=True)
        subprocess.run(f"chmod +x {file_path}", shell=True, check=True)
        if os.path.exists(f"{file_path}.tar.gz"): os.remove(f"{file_path}.tar.gz")
        return True
    except: return False

def install_local_rathole(config_data):
    if not check_binary("rathole"):
        raise Exception("Rathole binary missing.")
        
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
    with open(f"{INSTALL_DIR}/rathole_iran{port}.toml", "w") as f:
        f.write(config_content)

    svc_name = f"rathole-iran{port}"
    svc_content = f"""
[Unit]
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
    
    services = ""
    for p in config_data['ports']:
        services += f'\n[client.services.{p}]\ntype = "{config_data["transport"]}"\nlocal_addr = "0.0.0.0:{p}"\n'

    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/rathole ]; then
        curl -L -o {INSTALL_DIR}/rathole.tar.gz {REPO_URL}/rathole.tar.gz
        tar -xzf {INSTALL_DIR}/rathole.tar.gz -C {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/rathole
    fi

    cat > {INSTALL_DIR}/rathole_kharej{port}.toml <<EOL
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
ExecStart={INSTALL_DIR}/rathole {INSTALL_DIR}/rathole_kharej{port}.toml
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload
    systemctl enable rathole-kharej{port}
    systemctl restart rathole-kharej{port}
    """
    return run_remote_command(ssh_ip, remote_script)