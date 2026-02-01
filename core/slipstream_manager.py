import os
import subprocess
from core.ssh_manager import run_remote_command_iter, run_remote_command

INSTALL_DIR = "/root/slipstream"
REPO_URL = "https://github.com/Mygod/slipstream-rust.git"

def get_build_script():
    """
    اسکریپت نصب با سازگاری کامل POSIX (برای جلوگیری از خطای sh: source not found)
    """
    return f"""
    set -e  # توقف فوری در صورت بروز خطا

    # اطمینان از نصب ابزارها
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y cmake pkg-config libssl-dev git python3 build-essential -qq

    # اضافه کردن مسیر کارگو به متغیر محیطی (حیاتی برای پیدا شدن cargo)
    export PATH="$HOME/.cargo/bin:$PATH"

    # نصب Rust اگر نصب نباشد
    if ! command -v cargo > /dev/null 2>&1; then
        echo "Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        
        # لود کردن محیط راست
        if [ -f "$HOME/.cargo/env" ]; then
            . "$HOME/.cargo/env"
        fi
    fi

    # چک نهایی
    if ! command -v cargo > /dev/null 2>&1; then
        echo "Error: Cargo not found even after install. PATH issue."
        exit 1
    fi
    
    echo "Rust version: $(rustc --version)"

    # کلون و بیلد
    mkdir -p {INSTALL_DIR}
    if [ ! -d {INSTALL_DIR}/.git ]; then
        echo "Cloning repository..."
        rm -rf {INSTALL_DIR}
        git clone {REPO_URL} {INSTALL_DIR}
    fi

    cd {INSTALL_DIR}
    echo "Updating submodules (Picoquic)..."
    git submodule update --init --recursive
    
    echo "Building Release Binaries (This takes time)..."
    # PICOQUIC_AUTO_BUILD=1 به صورت پیش‌فرض فعال است
    cargo build --release -p slipstream-client -p slipstream-server
    """

def install_slipstream_server_remote_gen(ssh_ip, config):
    """Generator Function for Remote Install"""
    script = get_build_script()
    
    # مرحله 1: نصب و بیلد (استریم زنده)
    # از bash -c برای اطمینان از اجرای صحیح استفاده می‌کنیم
    wrapped_script = f"bash -c '{script}'"
    for log in run_remote_command_iter(ssh_ip, script):
        yield log

    # مرحله 2: ساخت سرویس (سریع)
    service_script = f"""
    export PATH="$HOME/.cargo/bin:$PATH"
    cd {INSTALL_DIR}
    
    # تولید گواهی
    if [ ! -f cert.pem ]; then
        openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 3650 -subj "/CN={config['domain']}"
    fi
    
    # فایروال
    ufw allow {config['tunnel_port']}/udp
    iptables -I INPUT -p udp --dport {config['tunnel_port']} -j ACCEPT 2>/dev/null
    
    # سرویس
    cat > /etc/systemd/system/slipstream-server.service <<EOL
[Unit]
Description=Slipstream Server
After=network.target
[Service]
WorkingDirectory={INSTALL_DIR}
ExecStart={INSTALL_DIR}/target/release/slipstream-server \\
  --dns-listen-port {config['tunnel_port']} \\
  --target-address 127.0.0.1:{config['dest_port']} \\
  --domain {config['domain']} \\
  --cert ./cert.pem \\
  --key ./key.pem \\
  --reset-seed ./reset-seed
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload && systemctl enable slipstream-server && systemctl restart slipstream-server
    echo "Server Service Started."
    """
    
    run_remote_command(ssh_ip, service_script)


def install_slipstream_client_local_gen(remote_ip, config):
    """Generator Function for Local Install"""
    
    # 1. بیلد لوکال
    # استفاده مستقیم از Popen با شل bash برای جلوگیری از مشکلات sh
    import subprocess
    script = get_build_script()
    
    # اجرای اسکریپت با bash صریح
    process = subprocess.Popen(
        ['/bin/bash', '-c', script],
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True
    )
    
    for line in iter(process.stdout.readline, ""):
        yield f"Local: {line.strip()}"
        
    process.wait()
    
    if process.returncode != 0:
        raise Exception("Local build failed. Check logs.")
    
    # 2. سرویس لوکال
    home_dir = os.path.expanduser("~")
    svc = f"""
[Unit]
Description=Slipstream Client
After=network.target
[Service]
WorkingDirectory={INSTALL_DIR}
# اضافه کردن مسیر Cargo به سرویس
Environment="PATH={os.environ['PATH']}:{home_dir}/.cargo/bin"
ExecStart={INSTALL_DIR}/target/release/slipstream-client \\
  --tcp-listen-port {config['client_port']} \\
  --resolver {remote_ip}:{config['tunnel_port']} \\
  --domain {config['domain']}
Restart=always
[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/slipstream-client.service", "w") as f:
        f.write(svc)
    
    os.system("systemctl daemon-reload && systemctl enable slipstream-client && systemctl restart slipstream-client")
    yield "Local Service Started."