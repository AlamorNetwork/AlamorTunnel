import os
import secrets
import logging
from core.ssh_manager import SSHManager

logger = logging.getLogger("BackhaulManager")
logger.setLevel(logging.INFO)

REMOTE_BIN_PATH = "/root/alamor/bin/backhaul"
REMOTE_CONFIG_PATH = "/root/alamor/bin/backhaul_server.toml"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/backhaul"
LOCAL_CONFIG_PATH = "/root/AlamorTunnel/bin/backhaul_client.toml"
# لینک دانلود اصلاح شده و مستقیم
DOWNLOAD_URL = "https://github.com/Musixal/Backhaul/releases/download/v0.6.0/backhaul_linux_amd64.tar.gz"

class BackhaulManager:
    def __init__(self):
        pass

    def _generate_token(self):
        return secrets.token_hex(16)

    def _generate_server_toml(self, config):
        bind_port = config.get('tunnel_port', 3080)
        transport = config.get('transport', 'tcp')
        token = config.get('token', self._generate_token())
        keepalive = config.get('keepalive_period', 75)
        heartbeat = config.get('heartbeat', 40)
        channel_size = config.get('channel_size', 2048)
        sniffer = str(config.get('sniffer', False)).lower()
        web_port = config.get('web_port', 2060)
        nodelay = str(config.get('nodelay', True)).lower()

        mux_block = ""
        if "mux" in transport:
            mux_block = f"""
    mux_con = {config.get('mux_con', 8)}
    mux_version = {config.get('mux_version', 1)}
    mux_framesize = {config.get('mux_framesize', 32768)}
    mux_recievebuffer = {config.get('mux_recievebuffer', 4194304)}
    mux_streambuffer = {config.get('mux_streambuffer', 65536)}"""

        tls_block = ""
        if "wss" in transport:
            tls_block = """
    tls_cert = "/root/alamor/certs/server.crt"
    tls_key = "/root/alamor/certs/server.key"
            """

        ports_list = []
        raw_ports = config.get('port_rules', [])
        for p in raw_ports:
            if p.strip():
                ports_list.append(f'"{p.strip()}"')
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
    {mux_block}
    {tls_block}
    ports = [{ports_str}]
    """
        return toml, token

    def _generate_client_toml(self, server_ip, config):
        bind_port = config.get('tunnel_port', 3080)
        transport = config.get('transport', 'tcp')
        token = config.get('token', '')
        
        mux_block = ""
        if "mux" in transport:
            mux_block = f"""
    mux_version = {config.get('mux_version', 1)}
    mux_framesize = {config.get('mux_framesize', 32768)}
    mux_recievebuffer = {config.get('mux_recievebuffer', 4194304)}
    mux_streambuffer = {config.get('mux_streambuffer', 65536)}"""

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
    {edge_ip_block}
    {mux_block}
    """
        return toml

    def install_server(self, server_ip, config):
        logger.info(f"Installing Backhaul Server on {server_ip}")
        
        ssh = SSHManager()
        ssh_port = int(config.get('ssh_port', 22))
        ssh_pass = config.get('ssh_pass')
        ssh_key = config.get('ssh_key')

        def run(step, cmd):
            ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port, ssh_key)
            if not ok:
                raise Exception(f"{step} Failed: {out}")
            return out

        try:
            run("Check Connection", "whoami")
            run("Install Deps", "export DEBIAN_FRONTEND=noninteractive; apt-get update -y && apt-get install -y openssl ca-certificates tar gzip curl")
            run("Mkdir", "mkdir -p /root/alamor/bin /root/alamor/certs")

            # Check Binary
            check_cmd = f"[ -f {REMOTE_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
            if "MISSING" in run("Check Binary", check_cmd):
                # دانلود و استخراج (اصلاح شده برای اطمینان از مسیر)
                dl_cmd = f"curl -L -k -o /tmp/backhaul.tar.gz {DOWNLOAD_URL} && tar -xzf /tmp/backhaul.tar.gz -C /root/alamor/bin/ && mv /root/alamor/bin/backhaul_linux_amd64 {REMOTE_BIN_PATH} 2>/dev/null || mv /root/alamor/bin/backhaul {REMOTE_BIN_PATH} && chmod +x {REMOTE_BIN_PATH}"
                run("Download Backhaul", dl_cmd)

            if "wss" in config.get('transport', ''):
                cert_cmd = "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj '/CN=www.bing.com' -keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
                run("Generate Certs", cert_cmd)

            toml_content, token = self._generate_server_toml(config)
            config['token'] = token
            
            # نوشتن فایل کانفیگ
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
        import subprocess
        try:
            if not os.path.exists(LOCAL_BIN_PATH):
                os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
                subprocess.run(f"curl -L -k -o /tmp/backhaul.tar.gz {DOWNLOAD_URL}", shell=True, check=True)
                subprocess.run(f"tar -xzf /tmp/backhaul.tar.gz -C /root/AlamorTunnel/bin/", shell=True, check=True)
                # هندل کردن تغییر نام احتمالی در آرشیو
                subprocess.run(f"mv /root/AlamorTunnel/bin/backhaul_linux_amd64 {LOCAL_BIN_PATH} 2>/dev/null || true", shell=True)
                subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

            toml_content = self._generate_client_toml(server_ip, config)
            
            # ذخیره با نام یونیک (برای پشتیبانی چند تانل)
            unique_config_path = f"/root/AlamorTunnel/bin/backhaul_client_{config.get('tunnel_port')}.toml"
            with open(unique_config_path, "w") as f:
                f.write(toml_content)

            svc_name = f"backhaul-client-{config.get('tunnel_port')}"
            svc_content = f"""[Unit]
Description=Backhaul Client {config.get('tunnel_port')}
After=network.target
[Service]
Type=simple
ExecStart={LOCAL_BIN_PATH} -c {unique_config_path}
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
"""
            with open(f"/etc/systemd/system/{svc_name}.service", "w") as f:
                f.write(svc_content)

            os.system(f"systemctl daemon-reload && systemctl restart {svc_name} && systemctl enable {svc_name}")
            return True, "Backhaul Client Installed"
        except Exception as e:
            logger.error(f"Local Client Error: {e}")
            return False, str(e)

# Global Functions required by routes
def install_remote_backhaul(server_ip, iran_ip, config):
    return BackhaulManager().install_server(server_ip, config)

def install_local_backhaul(config):
    # دریافت IP سرور از کانفیگ (که قبلاً ست شده)
    server_ip = config.get('ssh_ip', '127.0.0.1') 
    return BackhaulManager().install_client(server_ip, config)

def generate_token():
    return BackhaulManager()._generate_token()

def stop_and_delete_backhaul(port):
    svc_name = f"backhaul-client-{port}"
    os.system(f"systemctl stop {svc_name}")
    os.system(f"systemctl disable {svc_name}")
    os.system(f"rm /etc/systemd/system/{svc_name}.service")
    os.system("systemctl daemon-reload")