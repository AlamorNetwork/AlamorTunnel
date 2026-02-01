import os
import secrets
from core.ssh_manager import run_remote_command
from core.ssl_manager import generate_self_signed_cert

INSTALL_DIR = "/root/backhaul"
BIN_URL = "https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz"

def generate_token():
    return secrets.token_hex(16)

def install_local_backhaul(config):
    """
    نصب و کانفیگ سمت سرور ایران (Panel Server)
    """
    # 1. نصب باینری
    if not os.path.exists(f"{INSTALL_DIR}/backhaul"):
        os.system(f"mkdir -p {INSTALL_DIR}")
        os.system(f"curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}")
        os.system(f"tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}")
        os.system(f"chmod +x {INSTALL_DIR}/backhaul")

    # 2. مدیریت SSL برای WSS
    tls_lines = ""
    if config['transport'] in ["wss", "wssmux"]:
        # اگر کاربر WSS خواسته بود، سرتیفیکیت تولید کن
        generate_self_signed_cert("127.0.0.1")
        tls_lines = f'tls_cert = "{config["tls_cert"]}"\ntls_key = "{config["tls_key"]}"'

    # 3. فرمت‌دهی پورت‌ها برای TOML
    # پورت‌ها در لیست پایتون هستند، باید به فرمت ["port1", "port2"] تبدیل شوند
    port_rules = config.get('port_rules', [])
    formatted_ports = ",\n    ".join([f'"{p.strip()}"' for p in port_rules if p.strip()])

    # 4. ساخت فایل Config.toml سرور
    # مقادیر پیش‌فرض با مقادیر فرم جایگزین شده‌اند
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
sniffer_log = "{config.get('sniffer_log', '/root/log.json')}"
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
    with open(f"{INSTALL_DIR}/config.toml", "w") as f:
        f.write(config_content)

    # 5. ساخت سرویس Systemd
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

    # 6. باز کردن پورت‌ها در فایروال
    os.system(f"ufw allow {config['tunnel_port']}/tcp")
    os.system(f"ufw allow {config['tunnel_port']}/udp")
    
    # 7. اجرا
    os.system("systemctl daemon-reload && systemctl enable backhaul && systemctl restart backhaul")
    return True

def install_remote_backhaul(ssh_target_ip, iran_connect_ip, config):
    """
    نصب و کانفیگ سمت سرور خارج (Foreign Server / Client)
    """
    clean_ip = iran_connect_ip.strip()
    edge_line = f'edge_ip = "{config["edge_ip"]}"' if config.get('edge_ip') else ""
    
    # اسکریپت Bash که روی سرور خارج اجرا می‌شود
    remote_script = f"""
    # 1. دانلود و نصب
    mkdir -p {INSTALL_DIR}
    if [ ! -f {INSTALL_DIR}/backhaul ]; then
        curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}
        tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}
        chmod +x {INSTALL_DIR}/backhaul
    fi
    
    # 2. ساخت کانفیگ کلاینت
    # دقت کنید remote_addr باید به IP ایران اشاره کند
    cat > {INSTALL_DIR}/config.toml <<EOL
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
so_rcvbuf = {config.get('so_rcvbuf', 4194304)}  # استفاده از همان مقدار سرور یا پیش‌فرض
so_sndbuf = {config.get('so_sndbuf', 1048576)}
EOL

    # 3. ساخت سرویس Systemd
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

    # 4. اجرا
    systemctl daemon-reload
    systemctl enable backhaul
    systemctl restart backhaul
    """
    
    return run_remote_command(ssh_target_ip, remote_script)

def stop_and_delete_backhaul():
    """توقف و حذف سرویس لوکال"""
    os.system("systemctl stop backhaul && systemctl disable backhaul")
    os.system(f"rm -f {INSTALL_DIR}/config.toml")
    # فایل سرویس هم می‌تواند پاک شود
    return True