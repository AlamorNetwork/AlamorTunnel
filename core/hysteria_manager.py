import os
import secrets
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/hysteria"
BIN_URL = "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64"

def generate_pass():
    return secrets.token_hex(8)

def install_hysteria_core_local():
    """نصب هسته روی سرور ایران"""
    if not os.path.exists(f"{INSTALL_DIR}/hysteria"):
        print("[+] Installing Hysteria Core (Local)...")
        cmds = [
            f"mkdir -p {INSTALL_DIR}",
            f"curl -L -o {INSTALL_DIR}/hysteria {BIN_URL}",
            f"chmod +x {INSTALL_DIR}/hysteria"
        ]
        for cmd in cmds:
            os.system(cmd)

def install_hysteria_server_remote(ssh_target_ip, config_data):
    """
    نصب و راه اندازی سرور روی خارج
    شامل: دانلود، تولید سرتیفیکیت، کانفیگ و باز کردن فایروال
    """
    print(f"[+] Configuring Hysteria Server on {ssh_target_ip}...")
    
    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    
    # 1. دانلود هسته
    if [ ! -f {INSTALL_DIR}/hysteria ]; then
        curl -L -o {INSTALL_DIR}/hysteria {BIN_URL}
        chmod +x {INSTALL_DIR}/hysteria
    fi

    # 2. تولید سرتیفیکیت (Self-Signed)
    if [ ! -f {INSTALL_DIR}/server.crt ]; then
        openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
            -subj "/C=US/ST=CA/L=SF/O=Alamor/CN=bing.com" \
            -keyout {INSTALL_DIR}/server.key \
            -out {INSTALL_DIR}/server.crt
    fi

    # 3. ساخت کانفیگ سرور (YAML) - بدون Masquerade (تضمین پایداری)
    cat > {INSTALL_DIR}/config.yaml <<EOL
listen: :{config_data['tunnel_port']}

tls:
  cert: {INSTALL_DIR}/server.crt
  key: {INSTALL_DIR}/server.key

auth:
  type: password
  password: "{config_data['password']}"

obfs:
  type: salamander
  salamander:
    password: "{config_data['obfs_pass']}"
EOL

    # 4. ساخت سرویس
    cat > /etc/systemd/system/hysteria-server.service <<EOL
[Unit]
Description=Hysteria 2 Server
After=network.target

[Service]
Type=simple
ExecStart={INSTALL_DIR}/hysteria server -c {INSTALL_DIR}/config.yaml
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOL
    
    # 5. باز کردن فایروال (UDP و TCP)
    ufw allow {config_data['tunnel_port']}/udp
    ufw allow {config_data['tunnel_port']}/tcp
    iptables -I INPUT -p udp --dport {config_data['tunnel_port']} -j ACCEPT
    iptables -I INPUT -p tcp --dport {config_data['tunnel_port']} -j ACCEPT

    # 6. اجرای سرویس
    systemctl daemon-reload
    systemctl enable hysteria-server
    systemctl restart hysteria-server
    """
    
    return run_remote_command(ssh_target_ip, remote_script)

def install_hysteria_client_local(remote_ip, config_data):
    """
    نصب کلاینت روی سرور ایران
    """
    install_hysteria_core_local()
    
    # ساخت لیست فورواردینگ
    forward_rules = ""
    for port in config_data['ports']:
        forward_rules += f"""
  - listen: :{port}
    remote: 127.0.0.1:{port}
"""

    # ساخت کانفیگ کلاینت (YAML)
    config_content = f"""
server: {remote_ip}:{config_data['tunnel_port']}

auth: "{config_data['password']}"

tls:
  insecure: true
  sni: bing.com

obfs:
  type: salamander
  salamander:
    password: "{config_data['obfs_pass']}"

bandwidth:
  up: {config_data['up_mbps']} mbps
  down: {config_data['down_mbps']} mbps

tcpForwarding:
{forward_rules}

udpForwarding:
{forward_rules}
"""
    
    with open(f"{INSTALL_DIR}/client.yaml", "w") as f:
        f.write(config_content)

    # ساخت سرویس کلاینت
    service_content = f"""
[Unit]
Description=Hysteria 2 Client (Iran Tunnel)
After=network.target

[Service]
Type=simple
ExecStart={INSTALL_DIR}/hysteria client -c {INSTALL_DIR}/client.yaml
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/hysteria-client.service", "w") as f:
        f.write(service_content)

    os.system("systemctl daemon-reload && systemctl enable hysteria-client && systemctl restart hysteria-client")
    return True