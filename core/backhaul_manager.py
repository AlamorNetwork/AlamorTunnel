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
    # اینجا پورت‌ها باز می‌شوند و منتظر اتصال خارج می‌مانیم
    # ---------------------------------------------------------
    def _server_config_toml(self, config):
        tunnel_port = config.get('tunnel_port', 8080)
        token = config.get('token')
        transport = config.get('transport', 'tcp')
        
        # تعریف پورت‌های ورودی (که کاربر به آنها وصل می‌شود)
        # فرمت طبق داکیومنت: "PORT=127.0.0.1:PORT"
        # یعنی ترافیک وارده به پورت ایران را بفرست داخل تانل به سمت پورت لوکال خارج
        ports_list = []
        if 'port_rules' in config:
            # اگر کاربر لیستی از پورت‌ها داده باشد (مثلا 9096, 9097)
            # فرض می‌کنیم ورودی لیست رشته‌ای است یا با کاما جدا شده
            rules = config['port_rules']
            if isinstance(rules, str): rules = rules.split(',')
            
            for p in rules:
                p = str(p).strip()
                if p:
                    # مثال: "9096=127.0.0.1:9096"
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
    # اینجا به ایران وصل می‌شویم (Dial)
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
        
        # اسکریپت هوشمند: اول تمیزکاری، بعد نصب
        install_script = f"""
        # 1. CLEANUP (پاکسازی سرویس‌های قدیمی برای جلوگیری از تداخل)
        systemctl stop backhaul-server 2>/dev/null
        systemctl stop backhaul-client 2>/dev/null
        rm -f /etc/systemd/system/backhaul*.service
        killall -9 backhaul 2>/dev/null

        # 2. SETUP
        mkdir -p {REMOTE_BIN_DIR}
        if [ ! -f {REMOTE_BIN} ]; then
            curl -L -k -o /tmp/backhaul.tar.gz {DL_URL}
            tar -xzf /tmp/backhaul.tar.gz -C /tmp/
            mv /tmp/backhaul_linux_amd64 {REMOTE_BIN}
            chmod +x {REMOTE_BIN}
        fi

        # 3. CONFIG
        cat > {REMOTE_BIN_DIR}/backhaul_client.toml <<EOF
{toml_content}
EOF

        # 4. SERVICE (Client Mode)
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

        # 1. CLEANUP LOCAL (پاکسازی سرویس قدیمی روی ایران)
        os.system(f"systemctl stop backhaul-client-{tunnel_port} 2>/dev/null")
        os.system(f"systemctl disable backhaul-client-{tunnel_port} 2>/dev/null")
        os.system(f"rm -f /etc/systemd/system/backhaul-client-{tunnel_port}.service")

        # 2. SETUP
        if not os.path.exists(LOCAL_BIN):
            os.makedirs(LOCAL_BIN_DIR, exist_ok=True)
            os.system(f"curl -L -k -o /tmp/backhaul.tar.gz {DL_URL}")
            os.system(f"tar -xzf /tmp/backhaul.tar.gz -C /tmp/")
            os.system(f"mv /tmp/backhaul_linux_amd64 {LOCAL_BIN}")
            os.system(f"chmod +x {LOCAL_BIN}")

        if not config.get('token'):
            config['token'] = self._gen_token()

        # 3. CONFIG (Server Mode)
        toml_content = self._server_config_toml(config)
        config_path = f"{LOCAL_BIN_DIR}/backhaul_server_{tunnel_port}.toml"
        with open(config_path, "w") as f:
            f.write(toml_content)

        # 4. SERVICE
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

# تابع اصلی که پنل صدا می‌زند
def install_backhaul_bridge(remote_ip, iran_ip, config):
    mgr = BackhaulManager()
    
    # اول ایران (سرور) راه بیفتد
    ok_local, token = mgr.install_local(config)
    if not ok_local: return False, "Local Server Install Failed"
    
    config['token'] = token
    
    # بعد خارج (کلاینت) وصل شود
    return mgr.install_remote(remote_ip, iran_ip, config)