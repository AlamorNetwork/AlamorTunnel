import os
import secrets
import json
from core.ssh_manager import run_remote_command
from core.ssl_manager import generate_self_signed_cert

INSTALL_DIR = "/root/backhaul"
BIN_URL = "https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz"

def generate_token():
    return secrets.token_hex(16)

def install_local_backhaul(config_data):
    """
    نصب روی سرور ایران (Server Mode)
    config_data: دیکشنری شامل تمام تنظیمات
    """
    print(f"[+] Configuring Local Backhaul (Iran) | Transport: {config_data['transport']}")
    
    # 1. دانلود و نصب (اگر وجود نداشت)
    if not os.path.exists(f"{INSTALL_DIR}/backhaul"):
        cmds = [
            f"mkdir -p {INSTALL_DIR}",
            f"curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}",
            f"tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}",
            f"chmod +x {INSTALL_DIR}/backhaul"
        ]
        for cmd in cmds:
            os.system(cmd)

    # 2. مدیریت SSL (فقط اگر WSS/WSSMUX بود)
    tls_config = ""
    if config_data['transport'] in ["wss", "wssmux"]:
        success, crt, key = generate_self_signed_cert(domain_or_ip="localhost")
        if success:
            tls_config = f'tls_cert = "{crt}"\ntls_key = "{key}"'
        else:
            print("[-] SSL Generation Failed!")

    # 3. مدیریت پارامترهای اختیاری Mux
    mux_settings = ""
    if config_data['transport'] in ["tcpmux", "wsmux", "wssmux"]:
        mux_settings = f"""
mux_version = {config_data.get('mux_version', 1)}
mux_framesize = {config_data.get('mux_framesize', 32768)}
mux_recievebuffer = {config_data.get('mux_recievebuffer', 4194304)}
mux_streambuffer = {config_data.get('mux_streambuffer', 65536)}
"""

    # 4. فرمت کردن پورت‌ها
    port_rules = config_data.get('port_rules', [])
    formatted_ports = ",\n    ".join([f'"{p.strip()}"' for p in port_rules if p.strip()])

    # 5. ساخت کانفیگ ایران
    config_content = f"""
[server]
bind_addr = "0.0.0.0:{config_data['tunnel_port']}"
transport = "{config_data['transport']}"
accept_udp = {str(config_data.get('accept_udp', 'false')).lower()}
token = "{config_data['token']}"
keepalive_period = {config_data.get('keepalive_period', 75)}
nodelay = {str(config_data.get('nodelay', 'false')).lower()}
channel_size = {config_data.get('channel_size', 2048)}
heartbeat = {config_data.get('heartbeat', 40)}
mux_con = {config_data.get('mux_con', 8)}
sniffer = {str(config_data.get('sniffer', 'false')).lower()}
web_port = 2060
sniffer_log = "/root/backhaul.json"
log_level = "{config_data.get('log_level', 'info')}"
skip_optz = {str(config_data.get('skip_optz', 'true')).lower()}
mss = {config_data.get('mss', 1360)}
so_rcvbuf = {config_data.get('so_rcvbuf', 4194304)}
so_sndbuf = {config_data.get('so_sndbuf', 1048576)}
{tls_config}
{mux_settings}

ports = [
    {formatted_ports}
]
"""
    with open(f"{INSTALL_DIR}/config.toml", "w") as f:
        f.write(config_content)

    # 6. سرویس و اجرا
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
    """
    نصب روی سرور خارج (Client Mode)
    """
    print(f"[+] Configuring Remote Backhaul on {ssh_target_ip}")
    
    # تنظیمات Mux برای کلاینت
    mux_settings = ""
    if config_data['transport'] in ["tcpmux", "wsmux", "wssmux"]:
        mux_settings = f"""
mux_version = {config_data.get('mux_version', 1)}
mux_framesize = {config_data.get('mux_framesize', 32768)}
mux_recievebuffer = {config_data.get('mux_recievebuffer', 4194304)}
mux_streambuffer = {config_data.get('mux_streambuffer', 65536)}
"""

    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}
    tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}
    chmod +x {INSTALL_DIR}/backhaul
    
    cat > {INSTALL_DIR}/config.toml <<EOL
[client]
remote_addr = "{iran_connect_ip}:{config_data['tunnel_port']}"
transport = "{config_data['transport']}"
token = "{config_data['token']}"
connection_pool = {config_data.get('connection_pool', 8)}
aggressive_pool = {str(config_data.get('aggressive_pool', 'false')).lower()}
keepalive_period = {config_data.get('keepalive_period', 75)}
nodelay = {str(config_data.get('nodelay', 'false')).lower()}
retry_interval = {config_data.get('retry_interval', 3)}
dial_timeout = {config_data.get('dial_timeout', 10)}
sniffer = {str(config_data.get('sniffer', 'false')).lower()}
web_port = 2060
log_level = "{config_data.get('log_level', 'info')}"
skip_optz = {str(config_data.get('skip_optz', 'true')).lower()}
mss = {config_data.get('mss', 1360)}
so_rcvbuf = {config_data.get('so_rcvbuf', 1048576)}
so_sndbuf = {config_data.get('so_sndbuf', 4194304)}
{mux_settings}
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

def stop_and_delete_backhaul():
    """حذف تانل"""
    os.system("systemctl stop backhaul && systemctl disable backhaul")
    os.system(f"rm {INSTALL_DIR}/config.toml")
    return True