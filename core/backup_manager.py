import os
import secrets
import logging
from core.ssh_manager import SSHManager

logger = logging.getLogger("BackhaulManager")

# مسیرها
REMOTE_BIN_DIR = "/root/alamor/bin"
REMOTE_BIN = f"{REMOTE_BIN_DIR}/backhaul"
LOCAL_BIN_DIR = "/root/AlamorTunnel/bin"
LOCAL_BIN = f"{LOCAL_BIN_DIR}/backhaul"
DL_URL = "https://github.com/Musixal/Backhaul/releases/download/v0.6.0/backhaul_linux_amd64.tar.gz"

class BackhaulManager:
    def _gen_token(self):
        return secrets.token_hex(16)

    # ---------------------------------------------------------
    # تنظیمات سرور (IRAN - Server Role)
    # ---------------------------------------------------------
    def _server_config_toml(self, config):
        tunnel_port = config.get('tunnel_port', 8080)
        token = config.get('token')
        transport = config.get('transport', 'tcp')
        
        ports_list = []
        if 'port_rules' in config:
            rules = config['port_rules']
            if isinstance(rules, str): rules = rules.split(',')
            
            for p in rules:
                p = str(p).strip()
                if p:
                    # فرمت: "PORT=127.0.0.1:PORT"
                    ports_list.append(f'"{p}=127.0.0.1:{p}"')
        
        ports_str = ",".join(ports_list)
        
        toml = f"""[server]
bind_addr = "0.0.0.0:{tunnel_port}"
transport = "{transport}"
token = "{token}"
keepalive_period = 75
nodelay = true
heartbeat = 40
channel_size = 2048
sniffer = false
log_level = "info"

ports = [
    {ports_str}
]
"""
        return toml

    # ---------------------------------------------------------
    # تنظیمات کلاینت (FOREIGN - Client Role)
    # ---------------------------------------------------------
    def _client_config_toml(self, iran_ip, config):
        tunnel_port = config.get('tunnel_port', 8080)
        token = config.get('token')
        transport = config.get('transport', 'tcp')
        pool_size = config.get('connection_pool', 4)

        toml = f"""[client]
remote_addr = "{iran_ip}:{tunnel_port}"
transport = "{transport}"
token = "{token}"
connection_pool = {pool_size}
aggressive_pool = false
keepalive_period = 75
dial_timeout = 10
retry_interval = 3
nodelay = true
sniffer = false
log_level = "info"
"""
        return toml

    # =========================================================
    # نصب روی سرور خارج (Remote - Client)
    # =========================================================
    def install_remote(self, remote_ip, iran_ip, config):
        ssh = SSHManager()
        user = config.get('ssh_user', 'root')
        passw = config.get('ssh_pass')
        port = int(config.get('ssh_port', 22))
        key = config.get('ssh_key')

        toml_content = self._client_config_toml(iran_ip, config)
        
        install_script = f"""
        # CLEANUP
        systemctl stop backhaul-server 2>/dev/null
        systemctl stop backhaul-client 2>/dev/null
        rm -f /etc/systemd/system/backhaul*.service
        killall -9 backhaul 2>/dev/null

        # SETUP
        mkdir -p {REMOTE_BIN_DIR}
        if [ ! -f {REMOTE_BIN} ]; then
            curl -L -k -o /tmp/backhaul.tar.gz {DL_URL}
            tar -xzf /tmp/backhaul.tar.gz -C /tmp/
            mv /tmp/backhaul_linux_amd64 {REMOTE_BIN}
            chmod +x {REMOTE_BIN}
        fi

        # CONFIG
        cat > {REMOTE_BIN_DIR}/backhaul_client.toml <<EOF
{toml_content}
EOF

        # SERVICE
        cat > /etc/systemd/system/backhaul-client.service <<EOF
[Unit]
Description=Backhaul Client (Foreign -> Iran)
After=network.target

[Service]
ExecStart={REMOTE_BIN} -c {REMOTE_BIN_DIR}/backhaul_client.toml
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
EOF

        systemctl daemon-reload
        systemctl enable backhaul-client
        systemctl restart backhaul-client
        """
        
        return ssh.run_remote_command(remote_ip, user, passw, install_script, port, key)

    # =========================================================
    # نصب روی سرور ایران (Local - Server)
    # =========================================================
    def install_local(self, config):
        tunnel_port = config.get('tunnel_port', 8080)

        # CLEANUP LOCAL
        os.system(f"systemctl stop backhaul-client-{tunnel_port} 2>/dev/null")
        os.system(f"systemctl disable backhaul-client-{tunnel_port} 2>/dev/null")
        os.system(f"rm -f /etc/systemd/system/backhaul-client-{tunnel_port}.service")

        # SETUP
        if not os.path.exists(LOCAL_BIN):
            os.makedirs(LOCAL_BIN_DIR, exist_ok=True)
            os.system(f"curl -L -k -o /tmp/backhaul.tar.gz {DL_URL}")
            os.system(f"tar -xzf /tmp/backhaul.tar.gz -C /tmp/")
            os.system(f"mv /tmp/backhaul_linux_amd64 {LOCAL_BIN}")
            os.system(f"chmod +x {LOCAL_BIN}")

        if not config.get('token'):
            config['token'] = self._gen_token()

        # CONFIG
        toml_content = self._server_config_toml(config)
        config_path = f"{LOCAL_BIN_DIR}/backhaul_server_{tunnel_port}.toml"
        with open(config_path, "w") as f:
            f.write(toml_content)

        # SERVICE
        svc_name = f"backhaul-server-{tunnel_port}"
        svc_content = f"""[Unit]
Description=Backhaul Server (Iran) {tunnel_port}
After=network.target

[Service]
ExecStart={LOCAL_BIN} -c {config_path}
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
        with open(f"/etc/systemd/system/{svc_name}.service", "w") as f:
            f.write(svc_content)

        os.system(f"systemctl daemon-reload && systemctl enable {svc_name} && systemctl restart {svc_name}")
        return True, config['token']

# =========================================================
# GLOBAL EXPORTED FUNCTIONS (توابعی که ایمپورت می‌شوند)
# =========================================================

def install_backhaul_bridge(remote_ip, iran_ip, config):
    mgr = BackhaulManager()
    
    # 1. نصب سرور روی ایران
    ok_local, token = mgr.install_local(config)
    if not ok_local: return False, "Local Server Install Failed"
    
    config['token'] = token
    
    # 2. نصب کلاینت روی خارج
    return mgr.install_remote(remote_ip, iran_ip, config)

def generate_token():
    return secrets.token_hex(16)

def stop_and_delete_backhaul(port):
    try:
        # پاک کردن سرویس سرور ایران
        service_name = f"backhaul-server-{port}"
        os.system(f"systemctl stop {service_name} 2>/dev/null")
        os.system(f"systemctl disable {service_name} 2>/dev/null")
        
        # پاک کردن فایل سرویس
        svc_path = f"/etc/systemd/system/{service_name}.service"
        if os.path.exists(svc_path):
            os.remove(svc_path)
            
        # پاک کردن کانفیگ
        cfg_path = f"{LOCAL_BIN_DIR}/backhaul_server_{port}.toml"
        if os.path.exists(cfg_path):
            os.remove(cfg_path)

        os.system("systemctl daemon-reload")
        return True
    except Exception as e:
        logger.error(f"Delete Error: {e}")
        return False