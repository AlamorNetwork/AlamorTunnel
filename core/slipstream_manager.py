import os
import secrets
from core.ssh_manager import run_remote_command

# مسیر نصب
INSTALL_DIR = "/root/slipstream"
REPO_URL = "https://github.com/Mygod/slipstream-rust.git"

def install_rust_and_build(ssh_target_ip=None):
    """
    نصب پیش‌نیازها و بیلد کردن پروژه
    چون بیلد کردن طول می‌کشد، فقط یکبار انجام می‌شود.
    """
    setup_script = f"""
    # 1. نصب پیش‌نیازهای سیستمی
    apt-get update
    apt-get install -y cmake pkg-config libssl-dev git python3 build-essential

    # 2. نصب Rust (اگر نصب نباشد)
    if ! command -v cargo &> /dev/null; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi
    
    # اطمینان از لود شدن محیط Rust
    source "$HOME/.cargo/env"

    # 3. کلون کردن و بیلد کردن (فقط اگر فایل نهایی نباشد)
    if [ ! -f {INSTALL_DIR}/target/release/slipstream-server ]; then
        echo "[+] Cloning Slipstream..."
        rm -rf {INSTALL_DIR}
        git clone --recursive {REPO_URL} {INSTALL_DIR}
        
        echo "[+] Building Slipstream (This may take a while)..."
        cd {INSTALL_DIR}
        
        # بیلد کردن نسخه ریلیز
        cargo build --release -p slipstream-server -p slipstream-client
    fi
    """
    
    if ssh_target_ip:
        return run_remote_command(ssh_target_ip, setup_script)
    else:
        # لوکال (سرور ایران)
        os.system(setup_script)
        return True

def install_slipstream_server_remote(ssh_target_ip, config_data):
    """
    راه اندازی سرور روی خارج
    """
    print(f"[+] Setting up Slipstream Server on {ssh_target_ip}...")
    
    # 1. نصب و بیلد (اگر قبلا انجام نشده باشد)
    install_rust_and_build(ssh_target_ip)
    
    # 2. اسکریپت اجرای سرویس
    # نکته: Slipstream روی پورت DNS (UDP) گوش می‌دهد و ترافیک را به Xray (TCP) می‌دهد.
    remote_script = f"""
    source "$HOME/.cargo/env"
    cd {INSTALL_DIR}

    # تولید سرتیفیکیت (اگر نباشد)
    if [ ! -f cert.pem ]; then
        openssl req -x509 -newkey rsa:2048 -nodes \
          -keyout key.pem -out cert.pem -days 3650 \
          -subj "/CN={config_data['domain']}"
    fi
    
    # باز کردن پورت در فایروال
    ufw allow {config_data['tunnel_port']}/udp
    iptables -I INPUT -p udp --dport {config_data['tunnel_port']} -j ACCEPT

    # ساخت سرویس
    cat > /etc/systemd/system/slipstream-server.service <<EOL
[Unit]
Description=Slipstream DNS Tunnel Server
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}
ExecStart={INSTALL_DIR}/target/release/slipstream-server \\
  --dns-listen-port {config_data['tunnel_port']} \\
  --target-address 127.0.0.1:{config_data['dest_port']} \\
  --domain {config_data['domain']} \\
  --cert ./cert.pem \\
  --key ./key.pem

Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOL

    systemctl daemon-reload
    systemctl enable slipstream-server
    systemctl restart slipstream-server
    """
    
    return run_remote_command(ssh_target_ip, remote_script)

def install_slipstream_client_local(remote_ip, config_data):
    """
    راه اندازی کلاینت روی ایران
    """
    print("[+] Setting up Slipstream Client locally...")
    
    # 1. نصب و بیلد لوکال
    install_rust_and_build()
    
    # 2. ساخت سرویس کلاینت
    # کلاینت روی پورت TCP گوش می‌دهد (برای دریافت از کاربر) و می‌فرستد به DNS سرور خارج
    service_content = f"""
[Unit]
Description=Slipstream DNS Tunnel Client
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}
Environment="PATH={os.environ['PATH']}:/root/.cargo/bin"
ExecStart={INSTALL_DIR}/target/release/slipstream-client \\
  --tcp-listen-port {config_data['client_port']} \\
  --resolver {remote_ip}:{config_data['tunnel_port']} \\
  --domain {config_data['domain']}

Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
    
    with open("/etc/systemd/system/slipstream-client.service", "w") as f:
        f.write(service_content)

    os.system("systemctl daemon-reload && systemctl enable slipstream-client && systemctl restart slipstream-client")
    return True