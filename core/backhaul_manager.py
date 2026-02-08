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
    # تنظیمات سرور (این بخش روی ایران اجرا می‌شود)
    # طبق داک: ایران سرور است و پورت‌ها را گوش می‌دهد
    # ---------------------------------------------------------
    def _server_config_toml(self, config):
        tunnel_port = config.get('tunnel_port', 8080)
        token = config.get('token')
        transport = config.get('transport', 'tcp')
        
        # پورت‌هایی که باید فوروارد شوند
        # فرمت: "9096=127.0.0.1:9096" یعنی ترافیک 9096 ایران رو بفرست به 9096 لوکالِ سرور خارج
        ports_list = []
        if 'port_rules' in config:
            for p in config['port_rules']:
                if p.strip():
                    # فرض بر این است که مقصد در سرور خارج روی لوکال‌هاست گوش می‌دهد
                    ports_list.append(f'"{p.strip()}=127.0.0.1:{p.strip()}"')
        
        ports_str = ",".join(ports_list)

        # تنظیمات اضافی بر اساس داکیومنت
        nodelay = "true"  # برای کاهش تاخیر
        keepalive = config.get('keepalive', 75)
        
        toml = f"""[server]
bind_addr = "0.0.0.0:{tunnel_port}"
transport = "{transport}"
token = "{token}"
keepalive_period = {keepalive}
nodelay = {nodelay}
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
    # تنظیمات کلاینت (این بخش روی خارج اجرا می‌شود)
    # طبق داک: خارج کلاینت است و به ایران وصل می‌شود
    # ---------------------------------------------------------
    def _client_config_toml(self, iran_ip, config):
        tunnel_port = config.get('tunnel_port', 8080)
        token = config.get('token')
        transport = config.get('transport', 'tcp')
        
        # تنظیمات Pool برای سرعت بالاتر
        pool_size = config.get('connection_pool', 8)
        aggressive = "true" if config.get('aggressive', False) else "false"

        toml = f"""[client]
remote_addr = "{iran_ip}:{tunnel_port}"
transport = "{transport}"
token = "{token}"
connection_pool = {pool_size}
aggressive_pool = {aggressive}
keepalive_period = 75
dial_timeout = 10
retry_interval = 3
nodelay = true
sniffer = false
log_level = "info"
"""
        return toml

    # =========================================================
    # نصب روی سرور خارج (Remote - Client Role)
    # =========================================================
    def install_remote(self, remote_ip, iran_ip, config):
        ssh = SSHManager()
        user = config.get('ssh_user', 'root')
        password = config.get('ssh_pass')
        port = int(config.get('ssh_port', 22))
        ssh_key = config.get('ssh_key')

        # تولید کانفیگ کلاینت
        toml_content = self._client_config_toml(iran_ip, config)
        
        # اسکریپت نصب در خارج
        install_script = f"""
        mkdir -p {REMOTE_BIN_DIR}
        
        # دانلود باینری اگر وجود نداشت
        if [ ! -f {REMOTE_BIN} ]; then
            curl -L -k -o /tmp/backhaul.tar.gz {DL_URL}
            tar -xzf /tmp/backhaul.tar.gz -C /tmp/
            mv /tmp/backhaul_linux_amd64 {REMOTE_BIN}
            chmod +x {REMOTE_BIN}
        fi

        # نوشتن کانفیگ
        cat > {REMOTE_BIN_DIR}/backhaul_client.toml <<EOF
{toml_content}
EOF

        # ساخت سرویس (به عنوان کلاینت که به ایران وصل میشه)
        cat > /etc/systemd/system/backhaul-client.service <<EOF
[Unit]
Description=Backhaul Client (Foreign)
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
        
        return ssh.run_remote_command(remote_ip, user, password, install_script, port, ssh_key)

    # =========================================================
    # نصب روی سرور ایران (Local - Server Role)
    # =========================================================
    def install_local(self, config):
        # اطمینان از وجود پوشه
        if not os.path.exists(LOCAL_BIN_DIR):
            os.makedirs(LOCAL_BIN_DIR)

        # دانلود باینری لوکال اگر نیست
        if not os.path.exists(LOCAL_BIN):
            os.system(f"curl -L -k -o /tmp/backhaul.tar.gz {DL_URL}")
            os.system(f"tar -xzf /tmp/backhaul.tar.gz -C /tmp/")
            os.system(f"mv /tmp/backhaul_linux_amd64 {LOCAL_BIN}")
            os.system(f"chmod +x {LOCAL_BIN}")

        # تولید توکن اگر موجود نباشد
        if not config.get('token'):
            config['token'] = self._gen_token()

        # تولید کانفیگ سرور
        toml_content = self._server_config_toml(config)
        tunnel_port = config.get('tunnel_port', 8080)
        
        config_path = f"{LOCAL_BIN_DIR}/backhaul_server_{tunnel_port}.toml"
        with open(config_path, "w") as f:
            f.write(toml_content)

        # ساخت سرویس (به عنوان سرور که گوش میده)
        service_name = f"backhaul-server-{tunnel_port}"
        service_content = f"""[Unit]
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
        with open(f"/etc/systemd/system/{service_name}.service", "w") as f:
            f.write(service_content)

        os.system(f"systemctl daemon-reload && systemctl enable {service_name} && systemctl restart {service_name}")
        return True, config['token']

# =========================================================
# Wrapper Functions (برای استفاده در app.py)
# =========================================================

def install_backhaul_bridge(remote_ip, iran_ip, config):
    mgr = BackhaulManager()
    
    # 1. اول سمت ایران (سرور) نصب شود تا توکن تولید شود و آماده شنیدن باشد
    ok_local, token = mgr.install_local(config)
    if not ok_local:
        return False, "Local Install Failed"
    
    # اضافه کردن توکن به کانفیگ برای سمت خارج
    config['token'] = token
    
    # 2. حالا سمت خارج (کلاینت) نصب شود و به ایران وصل شود
    ok_remote, msg_remote = mgr.install_remote(remote_ip, iran_ip, config)
    
    if ok_remote:
        return True, "Tunnel Established Successfully (Reverse Mode)"
    else:
        return False, f"Remote Install Failed: {msg_remote}"