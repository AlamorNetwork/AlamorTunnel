import os
import subprocess
import logging
from core.ssh_manager import SSHManager

logger = logging.getLogger("GostManager")
logger.setLevel(logging.INFO)

REMOTE_BIN_PATH = "/root/alamor/bin/gost"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/gost"
DOWNLOAD_URL = "https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz"

class GostManager:
    def __init__(self):
        pass

    def _build_args(self, mode, config):
        args = []
        listen_proto = config.get('listen_proto', 'socks5') 
        bind_port = config.get('bind_port', 1080)
        target = f"/{config['target']}" if config.get('target') else ""
        extras = f"?{config['extras']}" if config.get('extras') else ""

        args.append(f'-L="{listen_proto}://:{bind_port}{target}{extras}"')

        if mode in ['forward', 'client']:
            server_ip = config.get('server_ip', '')
            server_port = config.get('server_port', '')
            forward_proto = config.get('forward_proto', 'socks5')
            
            auth = ""
            if config.get('user') and config.get('pass'):
                auth = f"{config['user']}:{config['pass']}@"
            
            args.append(f'-F="{forward_proto}://{auth}{server_ip}:{server_port}"')

        return " ".join(args)

    def check_local_binary(self):
        if not os.path.exists(LOCAL_BIN_PATH):
            logger.info("Downloading Gost locally...")
            os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
            subprocess.run(f"curl -L -k -o /tmp/gost.gz {DOWNLOAD_URL}", shell=True, check=True)
            subprocess.run("gzip -d -f /tmp/gost.gz", shell=True, check=True)
            subprocess.run(f"mv /tmp/gost {LOCAL_BIN_PATH}", shell=True, check=True)
            subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

    def install_client(self, server_ip, config):
        logger.info("Installing Gost Client Locally")
        try:
            self.check_local_binary()

            config['server_ip'] = server_ip
            # اگر آرگومان دستی نبود، بساز
            gost_cmd = config.get('gost_args') or self._build_args('client', config)

            # استفاده از پورت کلاینت برای نام سرویس جهت جلوگیری از تداخل
            client_port = config.get('bind_port', 1080)
            svc_name = f"gost-client-{client_port}"

            svc_content = f"""[Unit]
Description=Gost Client {client_port}
After=network.target
[Service]
Type=simple
ExecStart={LOCAL_BIN_PATH} {gost_cmd}
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
"""
            with open(f"/etc/systemd/system/{svc_name}.service", "w") as f:
                f.write(svc_content)

            os.system(f"systemctl daemon-reload && systemctl restart {svc_name} && systemctl enable {svc_name}")
            return True, "Gost Client Installed"

        except Exception as e:
            logger.error(f"Client Install Error: {e}")
            return False, str(e)

# --- GLOBAL FUNCTIONS (مورد نیاز routes/tunnels.py) ---

def install_gost_client_local(server_ip, config):
    # این تابع کلاس بالا را صدا می‌زند
    manager = GostManager()
    # نگاشت فیلدهای فرم به کانفیگ منیجر
    # در فرم معمولا 'client_port' داریم اما کلاس 'bind_port' میخواهد
    if 'client_port' in config:
        config['bind_port'] = config['client_port']
    
    # اگر پورت سرور در کانفیگ اصلی tunnel_port بود
    if 'tunnel_port' in config:
        config['server_port'] = config['tunnel_port']

    return manager.install_client(server_ip, config)

def install_gost_server_remote(ip, config):
    port = config.get('tunnel_port', 443)
    ssh_user = config.get('ssh_user', 'root')
    ssh_pass = config.get('ssh_pass')
    ssh_key = config.get('ssh_key')
    ssh_port = int(config.get('ssh_port', 22))
    
    # اسکریپت نصب در سرور خارج
    script = f"""
    mkdir -p /root/alamor/bin
    if [ ! -f /root/alamor/bin/gost ]; then
        curl -L -k -o /root/alamor/bin/gost.gz {DOWNLOAD_URL}
        gzip -d -f /root/alamor/bin/gost.gz
        chmod +x /root/alamor/bin/gost
    fi
    
    # ساخت سرویس
    cat > /etc/systemd/system/gost-server-{port}.service <<EOL
[Unit]
Description=Gost Server {port}
After=network.target
[Service]
ExecStart=/root/alamor/bin/gost -L=:{port}
Restart=always
[Install]
WantedBy=multi-user.target
EOL
    
    systemctl daemon-reload && systemctl enable gost-server-{port} && systemctl restart gost-server-{port}
    """
    
    ssh = SSHManager()
    return ssh.run_remote_command(ip, ssh_user, ssh_pass, script, ssh_port, ssh_key)