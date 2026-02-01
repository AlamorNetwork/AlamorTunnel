import os
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/gost"
DOWNLOAD_URL = "https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz"

def install_binary():
    return f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/gost ]; then
        wget -q -O {INSTALL_DIR}/gost.gz {DOWNLOAD_URL}
        gzip -d -f {INSTALL_DIR}/gost.gz
        chmod +x {INSTALL_DIR}/gost
    fi
    """

def install_gost_server_remote(ssh_ip, config):
    script = f"""
    {install_binary()}
    cd {INSTALL_DIR}
    if [ ! -f cert.pem ]; then
        openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj "/CN=bing.com" -keyout key.pem -out cert.pem
    fi
    ufw allow {config['tunnel_port']}/tcp
    iptables -I INPUT -p tcp --dport {config['tunnel_port']} -j ACCEPT 2>/dev/null
    
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
    os.system(install_binary())
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