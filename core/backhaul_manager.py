import os
import secrets
from core.ssh_manager import run_remote_command

# تنظیمات ثابت
INSTALL_DIR = "/root/backhaul"
BIN_URL = "https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz"

def generate_token():
    """تولید یک توکن تصادفی برای امنیت تانل"""
    return secrets.token_hex(16)

def install_local_backhaul(local_port, remote_port, remote_ip, token):
    """نصب کلاینت روی سرور ایران"""
    print("[+] Installing Local Backhaul (Iran)...")
    
    # دانلود و اکسترکت
    os.system(f"mkdir -p {INSTALL_DIR}")
    os.system(f"curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}")
    os.system(f"tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}")
    os.system(f"chmod +x {INSTALL_DIR}/backhaul")

    # ساخت فایل کانفیگ کلاینت
    config_content = f"""
[client]
remote_addr = "{remote_ip}:{remote_port}"
token = "{token}"
connection_pool = 8

[[tunnels]]
name = "alamor-tunnel"
local_port = {local_port}
remote_port = {local_port}
type = "tcp"
"""
    with open(f"{INSTALL_DIR}/config.toml", "w") as f:
        f.write(config_content)

    # ساخت سرویس Systemd
    service_content = f"""
[Unit]
Description=Backhaul Client Service
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

    # فعال‌سازی و اجرا
    os.system("systemctl daemon-reload && systemctl enable backhaul && systemctl restart backhaul")
    return True

def install_remote_backhaul(remote_ip, remote_port, token):
    """نصب سرور روی سرور خارج (از طریق SSH)"""
    print("[+] Installing Remote Backhaul (Foreign)...")
    
    # اسکریپت که باید در سرور خارج اجرا شود
    remote_script = f"""
    mkdir -p {INSTALL_DIR}
    curl -L -o {INSTALL_DIR}/backhaul.tar.gz {BIN_URL}
    tar -xzf {INSTALL_DIR}/backhaul.tar.gz -C {INSTALL_DIR}
    chmod +x {INSTALL_DIR}/backhaul
    
    # ساخت کانفیگ سرور
    cat > {INSTALL_DIR}/config.toml <<EOL
[server]
bind_addr = "0.0.0.0:{remote_port}"
token = "{token}"
transport = "tcp"
keepalive_period = 75
nodelay = true
heartbeat = 40
EOL

    # ساخت سرویس
    cat > /etc/systemd/system/backhaul.service <<EOL
[Unit]
Description=Backhaul Server Service
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
    
    # ارسال دستور به سرور خارج
    success, output = run_remote_command(remote_ip, remote_script)
    return success, output