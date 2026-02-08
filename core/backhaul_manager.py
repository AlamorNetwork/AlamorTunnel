import os
import secrets
import logging
from core.ssh_manager import SSHManager

# تنظیم لاگر
logger = logging.getLogger("BackhaulManager")
logger.setLevel(logging.INFO)

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
        return secrets.token_hex(16)

    def _generate_server_toml(self, config):
        """تولید کانفیگ سمت سرور (TOML)"""
        bind_port = config.get('tunnel_port', 3080)
        transport = config.get('transport', 'tcp')
        token = config.get('token', self._generate_token())
        
        # تنظیمات اختیاری با مقادیر پیش‌فرض
        keepalive = config.get('keepalive', 75)
        heartbeat = config.get('heartbeat', 40)
        channel_size = config.get('channel_size', 2048)
        sniffer = str(config.get('sniffer', False)).lower()
        web_port = config.get('web_port', 2060)
        nodelay = str(config.get('nodelay', True)).lower()

        # تنظیمات Multiplexing
        mux_block = ""
        if "mux" in transport:
            mux_block = f"""
    mux_con = {config.get('mux_con', 8)}
    mux_version = {config.get('mux_version', 1)}
    mux_framesize = 32768
    mux_recievebuffer = 4194304
    mux_streambuffer = 65536"""

        # تنظیمات TLS
        tls_block = ""
        if "wss" in transport:
            tls_block = """
    tls_cert = "/root/alamor/certs/server.crt"
    tls_key = "/root/alamor/certs/server.key"
            """

        # تنظیمات پورت‌ها
        ports_list = []
        raw_ports = config.get('ports', [])
        # تبدیل رشته به لیست اگر لازم باشد
        if isinstance(raw_ports, str):
            raw_ports = [p.strip() for p in raw_ports.split(',') if p.strip()]
        
        for p in raw_ports:
            ports_list.append(f'"{p}"')
        ports_str = ", ".join(ports_list)

        toml = f"""[server]
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
    {mux_block}
    {tls_block}

    ports = [{ports_str}]
    """
        return toml, token

    def _generate_client_toml(self, server_ip, config):
        """تولید کانفیگ سمت کلاینت (TOML)"""
        bind_port = config.get('tunnel_port', 3080)
        transport = config.get('transport', 'tcp')
        token = config.get('token', '')
        
        mux_block = ""
        if "mux" in transport:
            mux_block = f"""
    mux_version = {config.get('mux_version', 1)}
    mux_framesize = 32768
    mux_recievebuffer = 4194304
    mux_streambuffer = 65536"""

        edge_ip_block = ""
        if config.get('edge_ip'):
            edge_ip_block = f'edge_ip = "{config["edge_ip"]}"'

        toml = f"""[client]
    remote_addr = "{server_ip}:{bind_port}"
    transport = "{transport}"
    token = "{token}"
    connection_pool = {config.get('connection_pool', 8)}
    aggressive_pool = {str(config.get('aggressive_pool', False)).lower()}
    keepalive_period = 75
    dial_timeout = 10
    retry_interval = 3
    nodelay = true
    sniffer = false
    web_port = 0
    log_level = "info"
    skip_optz = true
    {edge_ip_block}
    {mux_block}
    """
        return toml

    def install_server(self, server_ip, config):
        logger.info(f"Installing Backhaul Server on {server_ip}")
        ssh = SSHManager()
        ssh_port = int(config.get('ssh_port', 22))
        ssh_pass = config.get('ssh_pass')

        def run(step, cmd):
            ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port)
            if not ok:
                raise Exception(f"{step} Failed: {out}")
            return out

        try:
            run("Check Connection", "whoami")
            run("Install Deps", "export DEBIAN_FRONTEND=noninteractive; apt-get update -y && apt-get install -y openssl ca-certificates tar gzip")
            run("Mkdir", "mkdir -p /root/alamor/bin /root/alamor/certs")

            # دانلود
            check_cmd = f"[ -f {REMOTE_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
            if "MISSING" in run("Check Binary", check_cmd):
                dl_cmd = f"curl -L -o /tmp/backhaul.tar.gz {DOWNLOAD_URL} && tar -xzf /tmp/backhaul.tar.gz -C /root/alamor/bin/ && mv /root/alamor/bin/backhaul_linux_amd64 {REMOTE_BIN_PATH} && chmod +x {REMOTE_BIN_PATH} && rm /tmp/backhaul.tar.gz"
                run("Download Backhaul", dl_cmd)

            # تولید سرتیفیکیت برای WSS
            if "wss" in config.get('transport', ''):
                cert_cmd = "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj '/CN=www.bing.com' -keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
                run("Generate Certs", cert_cmd)

            # کانفیگ و سرویس
            toml_content, token = self._generate_server_toml(config)
            config['token'] = token
            run("Write Config", f"cat <<EOF > {REMOTE_CONFIG_PATH}\n{toml_content}\nEOF")

            svc_content = f"""[Unit]
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
"""
            run("Service File", f"cat <<EOF > /etc/systemd/system/backhaul.service\n{svc_content}\nEOF")
            run("Start Service", "systemctl daemon-reload && systemctl restart backhaul && systemctl enable backhaul")
            
            return True, "Backhaul Server Installed"

        except Exception as e:
            logger.error(f"Install Error: {e}")
            return False, str(e)

    def install_client(self, server_ip, config):
        # این متد باید روی سرور ایران اجرا شود (Local Exec)
        import subprocess
        try:
            if not os.path.exists(LOCAL_BIN_PATH):
                os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
                subprocess.run(f"curl -L -o /tmp/backhaul.tar.gz {DOWNLOAD_URL}", shell=True, check=True)
                subprocess.run(f"tar -xzf /tmp/backhaul.tar.gz -C /root/AlamorTunnel/bin/", shell=True, check=True)
                subprocess.run(f"mv /root/AlamorTunnel/bin/backhaul_linux_amd64 {LOCAL_BIN_PATH}", shell=True, check=True)
                subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

            toml_content = self._generate_client_toml(server_ip, config)
            with open(LOCAL_CONFIG_PATH, "w") as f:
                f.write(toml_content)

            svc_content = f"""[Unit]
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
"""
            with open("/etc/systemd/system/backhaul-client.service", "w") as f:
                f.write(svc_content)

            os.system("systemctl daemon-reload && systemctl restart backhaul-client && systemctl enable backhaul-client")
            return True, "Backhaul Client Installed"
        except Exception as e:
            logger.error(f"Local Client Error: {e}")
            return False, str(e)