import os
import secrets
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/backhaul"
BIN_URL = "https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz"

def generate_token():
    return secrets.token_hex(16)

def install_local_backhaul(tunnel_port, token, transport, port_rules, mux_version):
    """
    نصب سمت ایران (Server Mode)
    port_rules: لیستی از رشته‌ها مثل ["443", "8080=80"]
    """
    print(f"[+] Iran Config | Transport: {transport} | Mux: v{mux_version}")
    
    # دانلود و نصب
    cmds = [
        f"mkdir -p {INSTALL_DIR}",
        f"curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}",
        f"tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}",
        f"chmod +x {INSTALL_DIR}/backhaul"
    ]
    for cmd in cmds:
        os.system(cmd)

    # تبدیل لیست پورت‌ها به فرمت آرایه TOML
    # مثال خروجی: "443", "80=8080"
    formatted_ports = ",\n    ".join([f'"{p.strip()}"' for p in port_rules if p.strip()])

    # تنظیمات TLS (فعلا خالی)
    tls_config = ""
    if transport in ["wss", "wssmux"]:
        tls_config = 'tls_cert = "/root/server.crt"\ntls_key = "/root/server.key"'

    config_content = f"""
[server]
bind_addr = "0.0.0.0:{tunnel_port}"
transport = "{transport}"
accept_udp = false
token = "{token}"
keepalive_period = 75
nodelay = false
channel_size = 2048
heartbeat = 40
mux_con = 8
mux_version = {mux_version}
sniffer = false
web_port = 2060
sniffer_log = "/root/backhaul.json"
log_level = "info"
mss = 1360
so_rcvbuf = 4194304
so_sndbuf = 1048576
{tls_config}

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

def install_remote_backhaul(ssh_target_ip, iran_connect_ip, tunnel_port, token, transport, mux_version):
    """
    نصب سمت خارج (Client Mode)
    """
    print(f"[+] Foreign Config | Connect to: {iran_connect_ip}:{tunnel_port}")
    
    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}
    tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}
    chmod +x {INSTALL_DIR}/backhaul
    
    cat > {INSTALL_DIR}/config.toml <<EOL
[client]
remote_addr = "{iran_connect_ip}:{tunnel_port}"
transport = "{transport}"
token = "{token}"
connection_pool = 8
aggressive_pool = false
keepalive_period = 75
nodelay = false
retry_interval = 3
dial_timeout = 10
mux_version = {mux_version}
sniffer = false
web_port = 2060
log_level = "info"
mss = 1360
so_rcvbuf = 1048576
so_sndbuf = 4194304
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
    
    success, output = run_remote_command(ssh_target_ip, remote_script)
    return success, output