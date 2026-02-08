import os
import logging
import subprocess
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

    def install_server(self, server_ip, config):
        logger.info(f"Installing Gost Server on {server_ip}")
        
        # اصلاح مهم: ساخت نمونه از کلاس SSHManager
        ssh = SSHManager()
        ssh_port = int(config.get('ssh_port', 22))
        ssh_pass = config.get('ssh_pass')

        def run(step, cmd):
            # فراخوانی متد روی آبجکت ssh
            ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port)
            if not ok:
                raise Exception(f"{step} Failed: {out}")
            return out

        try:
            run("Check Connection", "whoami")
            run("Mkdir", "mkdir -p /root/alamor/bin")

            check_cmd = f"[ -f {REMOTE_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
            if "MISSING" in run("Check Binary", check_cmd):
                dl_cmd = f"curl -L -o /tmp/gost.gz {DOWNLOAD_URL} && gzip -d -f /tmp/gost.gz && mv /tmp/gost {REMOTE_BIN_PATH} && chmod +x {REMOTE_BIN_PATH}"
                run("Download Gost", dl_cmd)

            gost_cmd = config.get('gost_args') or self._build_args('server', config)

            svc_content = f"""[Unit]
Description=Gost Server
After=network.target
[Service]
Type=simple
ExecStart={REMOTE_BIN_PATH} {gost_cmd}
Restart=always
RestartSec=3
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
"""
            run("Service File", f"cat <<EOF > /etc/systemd/system/gost.service\n{svc_content}\nEOF")
            run("Start Service", "systemctl daemon-reload && systemctl restart gost && systemctl enable gost")

            return True, "Gost Server Installed"

        except Exception as e:
            logger.error(f"Server Install Error: {e}")
            return False, str(e)

    def install_client(self, server_ip, config):
        logger.info("Installing Gost Client Locally")
        try:
            if not os.path.exists(LOCAL_BIN_PATH):
                os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
                subprocess.run(f"curl -L -o /tmp/gost.gz {DOWNLOAD_URL}", shell=True, check=True)
                subprocess.run("gzip -d -f /tmp/gost.gz", shell=True, check=True)
                subprocess.run(f"mv /tmp/gost {LOCAL_BIN_PATH}", shell=True, check=True)
                subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

            config['server_ip'] = server_ip
            gost_cmd = config.get('gost_args') or self._build_args('client', config)

            svc_content = f"""[Unit]
Description=Gost Client (Iran)
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
            with open("/etc/systemd/system/gost-client.service", "w") as f:
                f.write(svc_content)

            os.system("systemctl daemon-reload && systemctl restart gost-client && systemctl enable gost-client")
            return True, "Gost Client Installed"

        except Exception as e:
            logger.error(f"Client Install Error: {e}")
            return False, str(e)