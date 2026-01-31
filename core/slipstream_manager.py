import os
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/slipstream"
REPO_URL = "https://github.com/Mygod/slipstream-rust.git"

def install_rust_and_build(ssh_target_ip=None):
    """
    نصب پیش‌نیازها و بیلد کردن پروژه Slipstream Rust
    طبق داکیومنت: نیاز به submodule update و cmake و openssl دارد.
    """
    setup_script = f"""
    # 1. نصب پکیج‌های سیستمی
    apt-get update
    apt-get install -y cmake pkg-config libssl-dev git python3 build-essential

    # 2. نصب Rust (اگر نصب نباشد)
    if ! command -v cargo &> /dev/null; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi
    
    source "$HOME/.cargo/env"

    # 3. کلون و بیلد (اگر فایل نهایی نباشد)
    if [ ! -f {INSTALL_DIR}/target/release/slipstream-server ]; then
        echo "[+] Cloning Slipstream Repository..."
        rm -rf {INSTALL_DIR}
        git clone {REPO_URL} {INSTALL_DIR}
        
        cd {INSTALL_DIR}
        echo "[+] Initializing Submodules (Picoquic)..."
        git submodule update --init --recursive
        
        echo "[+] Building Release Binaries..."
        # طبق داکیومنت: PICOQUIC_AUTO_BUILD برای بیلد خودکار
        cargo build --release -p slipstream-client -p slipstream-server
    fi
    """
    
    if ssh_target_ip:
        return run_remote_command(ssh_target_ip, setup_script)
    else:
        # اجرا روی سرور لوکال (ایران)
        os.system(setup_script)
        return True

def install_slipstream_server_remote(ssh_target_ip, config):
    """
    کانفیگ سرور خارج (Server Mode)
    """
    print(f"[+] Configuring Slipstream Server on {ssh_target_ip}...")
    
    # 1. نصب و بیلد
    success, output = install_rust_and_build(ssh_target_ip)
    if not success: return False, output

    # 2. اسکریپت سرویس
    # پارامترها طبق داکیومنت: --dns-listen-port, --target-address, --domain
    remote_script = f"""
    source "$HOME/.cargo/env"
    cd {INSTALL_DIR}

    # تولید سرتیفیکیت (اگر نباشد)
    # طبق داکیومنت: اگر نباشد خود سرور می‌سازد ولی دستی می‌سازیم که کنترل داشته باشیم
    if [ ! -f cert.pem ]; then
        openssl req -x509 -newkey rsa:2048 -nodes \\
          -keyout key.pem -out cert.pem -days 3650 \\
          -subj "/CN={config['domain']}"
    fi
    
    # باز کردن پورت UDP در فایروال
    ufw allow {config['tunnel_port']}/udp
    iptables -I INPUT -p udp --dport {config['tunnel_port']} -j ACCEPT

    # ساخت سرویس
    cat > /etc/systemd/system/slipstream-server.service <<EOL
[Unit]
Description=Slipstream Rust Server
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}
ExecStart={INSTALL_DIR}/target/release/slipstream-server \\
  --dns-listen-port {config['tunnel_port']} \\
  --target-address 127.0.0.1:{config['dest_port']} \\
  --domain {config['domain']} \\
  --cert ./cert.pem \\
  --key ./key.pem \\
  --reset-seed ./reset-seed

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

def install_slipstream_client_local(remote_ip, config):
    """
    کانفیگ کلاینت روی ایران (Client Mode)
    """
    print("[+] Configuring Slipstream Client locally...")
    
    # 1. نصب و بیلد لوکال
    install_rust_and_build()
    
    home_dir = os.path.expanduser("~")
    
    # 2. ساخت سرویس کلاینت
    # پارامترها: --tcp-listen-port, --resolver (IP:UDP_PORT), --domain
    service_content = f"""
[Unit]
Description=Slipstream Rust Client
After=network.target

[Service]
Type=simple
WorkingDirectory={INSTALL_DIR}
Environment="PATH={os.environ['PATH']}:{home_dir}/.cargo/bin"
ExecStart={INSTALL_DIR}/target/release/slipstream-client \\
  --tcp-listen-port {config['client_port']} \\
  --resolver {remote_ip}:{config['tunnel_port']} \\
  --domain {config['domain']}

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