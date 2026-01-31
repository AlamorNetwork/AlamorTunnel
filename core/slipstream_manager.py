import os
from core.ssh_manager import run_remote_command

INSTALL_DIR = "/root/slipstream"
REPO_URL = "https://github.com/Mygod/slipstream-rust.git"

def install_remote_deps(ssh_ip):
    # نصب پیش‌نیازها و Rust روی سرور خارج
    script = f"""
    apt-get update
    apt-get install -y cmake pkg-config libssl-dev git build-essential
    if ! command -v cargo; then
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    fi
    source "$HOME/.cargo/env"
    if [ ! -d {INSTALL_DIR} ]; then
        git clone --recursive {REPO_URL} {INSTALL_DIR}
        cd {INSTALL_DIR}
        # بیلد کردن سرور
        cargo build --release -p slipstream-server
    fi
    """
    return run_remote_command(ssh_ip, script)

def install_slipstream_server_remote(ssh_ip, config):
    install_remote_deps(ssh_ip)
    script = f"""
    source "$HOME/.cargo/env"
    cd {INSTALL_DIR}
    if [ ! -f cert.pem ]; then
        openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 3650 -subj "/CN={config['domain']}"
    fi
    ufw allow {config['tunnel_port']}/udp
    
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
  --key ./key.pem
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    systemctl daemon-reload && systemctl enable slipstream-server && systemctl restart slipstream-server
    """
    return run_remote_command(ssh_ip, script)

def install_slipstream_client_local(remote_ip, config):
    # نصب لوکال
    os.system("apt-get install -y cmake pkg-config libssl-dev git build-essential")
    if os.system("command -v cargo") != 0:
        os.system("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y")
    
    home = os.path.expanduser("~")
    env_path = f"{home}/.cargo/bin"
    
    if not os.path.exists(INSTALL_DIR):
        os.system(f"git clone --recursive {REPO_URL} {INSTALL_DIR}")
        # بیلد کلاینت
        os.system(f"export PATH=$PATH:{env_path} && cd {INSTALL_DIR} && cargo build --release -p slipstream-client")

    svc = f"""
[Unit]
Description=Slipstream Client
After=network.target
[Service]
WorkingDirectory={INSTALL_DIR}
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:{env_path}"
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
    return True