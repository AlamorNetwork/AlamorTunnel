import os
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/gost"
# لینک دانلود نسخه 2.11.5 (نسخه پایدار و محبوب)
DOWNLOAD_URL = "https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz"

def install_gost_binary():
    """دستورات نصب باینری"""
    return f"""
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/gost ]; then
        echo "Downloading GOST..."
        wget -q -O {INSTALL_DIR}/gost.gz {DOWNLOAD_URL}
        gzip -d -f {INSTALL_DIR}/gost.gz
        chmod +x {INSTALL_DIR}/gost
    fi
    """

def install_gost_server_remote(ssh_ip, config):
    """
    کانفیگ سرور خارج (Relay Server)
    Gost Listen: relay+tls://:TUNNEL_PORT
    """
    print(f"[+] Configuring GOST Remote on {ssh_ip}...")
    
    install_cmd = install_gost_binary()
    
    # ساخت گواهی برای TLS (اگر نباشد)
    cert_cmd = f"""
    cd {INSTALL_DIR}
    if [ ! -f cert.pem ]; then
        openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
            -subj "/C=US/ST=CA/L=SF/O=Gost/CN=bing.com" \
            -keyout key.pem -out cert.pem
    fi
    """

    # دستور اجرا در سرور خارج
    # مد Relay+TLS برای امنیت و مخفی‌سازی
    exec_cmd = f"{INSTALL_DIR}/gost -L=relay+tls://:{config['tunnel_port']}?cert={INSTALL_DIR}/cert.pem&key={INSTALL_DIR}/key.pem"

    service_script = f"""
    {install_cmd}
    {cert_cmd}
    
    # Firewall
    ufw allow {config['tunnel_port']}/tcp
    iptables -I INPUT -p tcp --dport {config['tunnel_port']} -j ACCEPT 2>/dev/null

    # Service
    cat > /etc/systemd/system/gost-server.service <<EOL
[Unit]
Description=GOST Relay Server
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}
ExecStart={exec_cmd}
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOL

    systemctl daemon-reload && systemctl enable gost-server && systemctl restart gost-server
    echo "GOST Remote Service Started."
    """
    
    return run_remote_command(ssh_ip, service_script)

def install_gost_client_local(remote_ip, config):
    """
    کانفیگ سرور ایران (Local Forwarder)
    Gost Forward: tcp://:CLIENT_PORT/127.0.0.1:DEST_PORT -F=relay+tls://REMOTE_IP:TUNNEL_PORT
    """
    print("[+] Configuring GOST Local...")
    
    # نصب لوکال
    os.system(install_gost_binary())
    
    # دستور اجرا در ایران
    # ترافیک را از client_port می‌گیرد و می‌فرستد به dest_port در سرور خارج
    exec_cmd = f"{INSTALL_DIR}/gost -L=tcp://:{config['client_port']}/127.0.0.1:{config['dest_port']} -F=relay+tls://{remote_ip}:{config['tunnel_port']}?secure=true"

    service_content = f"""
[Unit]
Description=GOST Local Client
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}
ExecStart={exec_cmd}
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
    
    with open("/etc/systemd/system/gost-client.service", "w") as f:
        f.write(service_content)

    os.system("systemctl daemon-reload && systemctl enable gost-client && systemctl restart gost-client")
    return True