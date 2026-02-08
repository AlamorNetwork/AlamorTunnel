import os
import secrets
import logging
import subprocess
from core.ssh_manager import SSHManager

# تنظیمات لاگ
logger = logging.getLogger("BackhaulManager")

# ثابت‌ها
REMOTE_BIN_PATH = "/root/alamor/bin/backhaul"
REMOTE_CONFIG_PATH = "/root/alamor/bin/backhaul_server.toml"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/backhaul"
LOCAL_CONFIG_PATH = "/root/AlamorTunnel/bin/backhaul_client.toml"
DOWNLOAD_URL = "https://github.com/musixal/backhaul/releases/download/v0.6.0/backhaul_linux_amd64.tar.gz"

class BackhaulManager:
    def __init__(self):
        pass

    def _generate_token(self):
        """تولید توکن امن ۱۶ رقمی"""
        return secrets.token_hex(16)

    def _generate_server_toml(self, config):
        """
        تولید فایل کانفیگ TOML برای سرور بر اساس داکیومنت Backhaul
        """
        # تنظیمات عمومی
        bind_port = config.get('tunnel_port', 3080)
        transport = config.get('transport', 'tcp')  # tcp, tcpmux, ws, wss, wsmux
        token = config.get('token', self._generate_token())
        channel_size = config.get('channel_size', 2048)
        keepalive = config.get('keepalive', 75)
        heartbeat = config.get('heartbeat', 40)
        nodelay = str(config.get('nodelay', True)).lower()
        sniffer = str(config.get('sniffer', False)).lower()
        web_port = config.get('web_port', 2060)
        
        # تنظیمات TLS (فقط برای wss/wssmux)
        tls_section = ""
        if "wss" in transport:
            tls_section = f'''
tls_cert = "/root/alamor/certs/server.crt"
tls_key = "/root/alamor/certs/server.key"'''

        # تنظیمات Multiplexing (SMUX)
        mux_section = ""
        if "mux" in transport:
            mux_section = f'''
mux_con = {config.get('mux_con', 8)}
mux_version = {config.get('mux_version', 1)}
mux_framesize = 32768
mux_recievebuffer = 4194304
mux_streambuffer = 65536'''

        # تنظیمات پورت‌ها (Forwarding Rules)
        # فرمت ورودی: لیست یا رشته جدا شده با کاما
        # مثال: "443=1.1.1.1:5201", "80"
        ports_list = []
        raw_ports = config.get('ports', [])
        if isinstance(raw_ports, str):
            raw_ports = raw_ports.split(',')
        
        for p in raw_ports:
            p = p.strip()
            if p:
                ports_list.append(f'"{p}"')
        
        ports_str = ", ".join(ports_list)

        # ساخت محتوای TOML
        toml = f'''[server]
bind_addr = "0.0.0.0:{bind_port}"
transport = "{transport}"
token = "{token}"
keepalive_period = {keepalive}
nodelay = {nodelay}
heartbeat = {heartbeat}
channel_size = {channel_size}
sniffer = {sniffer}
web_port = {web_port}
sniffer_log = "/root/alamor/backhaul.json"
log_level = "info"
skip_optz = true
{mux_section}
{tls_section}

ports = [{ports_str}]
'''
        return toml, token

    def _generate_client_toml(self, server_ip, config):
        """
        تولید فایل کانفیگ TOML برای کلاینت
        """
        bind_port = config.get('tunnel_port', 3080)
        transport = config.get('transport', 'tcp')
        token = config.get('token', '')
        pool = config.get('connection_pool', 8)
        aggressive = str(config.get('aggressive_pool', False)).lower()
        nodelay = str(config.get('nodelay', True)).lower()
        retry = config.get('retry_interval', 3)
        dial_timeout = config.get('dial_timeout', 10)
        sniffer = str(config.get('sniffer', False)).lower()

        # تنظیمات Mux
        mux_section = ""
        if "mux" in transport:
            mux_section = f'''
mux_version = {config.get('mux_version', 1)}
mux_framesize = 32768
mux_recievebuffer = 4194304
mux_streambuffer = 65536'''

        # تنظیمات Edge IP (برای CDN)
        edge_ip_line = ""
        if config.get('edge_ip'):
            edge_ip_line = f'edge_ip = "{config["edge_ip"]}"'

        toml = f'''[client]
remote_addr = "{server_ip}:{bind_port}"
transport = "{transport}"
token = "{token}"
connection_pool = {pool}
aggressive_pool = {aggressive}
keepalive_period = 75
dial_timeout = {dial_timeout}
retry_interval = {retry}
nodelay = {nodelay}
sniffer = {sniffer}
web_port = 0
log_level = "info"
skip_optz = true
{edge_ip_line}
{mux_section}
'''
        return toml

    def install_server(self, server_ip, config):
        """نصب و راه‌اندازی سرور Backhaul روی سرور خارج"""
        logger.info(f"Installing Backhaul Server on {server_ip}")
        ssh = SSHManager()
        ssh_port = int(config.get('ssh_port', 22))
        ssh_pass = config.get('ssh_pass')

        def run(step, cmd):
            logger.info(f"STEP: {step}")
            ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port)
            if not ok:
                raise Exception(f"{step} Failed: {out}")
            return out

        try:
            # 1. بررسی اتصال
            run("Check Connection", "whoami")

            # 2. نصب پیش‌نیازها
            run("Install Deps", "export DEBIAN_FRONTEND=noninteractive; apt-get update -y && apt-get install -y openssl ca-certificates tar gzip")

            # 3. ایجاد دایرکتوری‌ها
            run("Mkdir", "mkdir -p /root/alamor/bin /root/alamor/certs")

            # 4. دانلود باینری (اگر وجود نداشت)
            check_cmd = f"[ -f {REMOTE_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
            if "MISSING" in run("Check Binary", check_cmd):
                dl_cmd = f"curl -L -o /tmp/backhaul.tar.gz {DOWNLOAD_URL} && tar -xzf /tmp/backhaul.tar.gz -C /root/alamor/bin/ && mv /root/alamor/bin/backhaul_linux_amd64 {REMOTE_BIN_PATH} && chmod +x {REMOTE_BIN_PATH} && rm /tmp/backhaul.tar.gz"
                run("Download Backhaul", dl_cmd)

            # 5. تولید سرتیفیکیت (اگر ترنسپورت WSS باشد)
            if "wss" in config.get('transport', ''):
                cert_cmd = "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj '/CN=www.bing.com' -keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
                run("Generate Certs", cert_cmd)

            # 6. تولید و آپلود کانفیگ
            toml_content, token = self._generate_server_toml(config)
            config['token'] = token # ذخیره توکن برای استفاده در کلاینت
            run("Write Config", f"cat <<EOF > {REMOTE_CONFIG_PATH}\n{toml_content}\nEOF")

            # 7. ساخت فایل سرویس
            svc_content = f'''[Unit]
Description=Backhaul Server
After=network.target

[Service]
Type=simple
ExecStart={REMOTE_BIN_PATH} -c {REMOTE_CONFIG_PATH}
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
'''
            run("Create Service", f"cat <<EOF > /etc/systemd/system/backhaul.service\n{svc_content}\nEOF")

            # 8. استارت سرویس
            run("Start Service", "systemctl daemon-reload && systemctl restart backhaul && systemctl enable backhaul")
            
            return True, "Backhaul Server Installed Successfully"

        except Exception as e:
            logger.error(f"Installation Error: {e}")
            return False, str(e)

    def install_client(self, server_ip, config):
        """نصب و راه‌اندازی کلاینت Backhaul روی سرور لوکال (ایران)"""
        logger.info("Installing Backhaul Client Locally")
        try:
            # 1. دانلود باینری
            if not os.path.exists(LOCAL_BIN_PATH):
                os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
                subprocess.run(f"curl -L -o /tmp/backhaul.tar.gz {DOWNLOAD_URL}", shell=True, check=True)
                subprocess.run(f"tar -xzf /tmp/backhaul.tar.gz -C /root/AlamorTunnel/bin/", shell=True, check=True)
                subprocess.run(f"mv /root/AlamorTunnel/bin/backhaul_linux_amd64 {LOCAL_BIN_PATH}", shell=True, check=True)
                subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)
                subprocess.run("rm /tmp/backhaul.tar.gz", shell=True)

            # 2. تولید کانفیگ
            toml_content = self._generate_client_toml(server_ip, config)
            with open(LOCAL_CONFIG_PATH, "w") as f:
                f.write(toml_content)

            # 3. ساخت سرویس
            svc_content = f'''[Unit]
Description=Backhaul Client (Iran)
After=network.target

[Service]
Type=simple
ExecStart={LOCAL_BIN_PATH} -c {LOCAL_CONFIG_PATH}
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
'''
            with open("/etc/systemd/system/backhaul-client.service", "w") as f:
                f.write(svc_content)

            # 4. استارت سرویس
            os.system("systemctl daemon-reload")
            os.system("systemctl enable backhaul-client")
            os.system("systemctl restart backhaul-client")

            return True, "Backhaul Client Installed Successfully"

        except Exception as e:
            logger.error(f"Local Install Error: {e}")
            return False, str(e)