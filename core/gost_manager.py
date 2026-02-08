import os
import logging
import subprocess
from core.ssh_manager import SSHManager

# تنظیمات لاگ
logger = logging.getLogger("GostManager")

# ثابت‌ها
REMOTE_BIN_PATH = "/root/alamor/bin/gost"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/gost"
DOWNLOAD_URL = "https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz"

class GostManager:
    def __init__(self):
        pass

    def _build_args(self, mode, config):
        """
        ساخت آرگومان‌های خط فرمان Gost بر اساس داکیومنت
        Modes: 
        - simple: پروکسی ساده (-L)
        - forward: فورواردینگ ساده (-L ... -F ...)
        - reverse: تانل معکوس (-L rtcp://...)
        - relay: زنجیره پروکسی (-F ... -F ...)
        """
        args = []
        
        # 1. Listen Node (-L)
        listen_proto = config.get('listen_proto', 'socks5') # tcp, udp, rtcp, rudp, tls, ws...
        bind_ip = config.get('bind_ip', '') # خالی یعنی همه اینترفیس‌ها
        bind_port = config.get('bind_port', 1080)
        
        # برای پورت فورواردینگ (مثلا tcp://:2222/1.1.1.1:22)
        target = config.get('target', '') 
        if target:
            target = f"/{target}"
        
        # پارامترهای اضافی (مثل ?cert=... یا ?ttl=...)
        extras = config.get('extras', '')
        if extras and not extras.startswith('?'):
            extras = f"?{extras}"

        # ساخت رشته Listen
        # مثال: -L=socks5://:1080
        # مثال: -L=rtcp://:2222/127.0.0.1:22
        args.append(f'-L="{listen_proto}://{bind_ip}:{bind_port}{target}{extras}"')

        # 2. Forward Node (-F) - اختیاری
        # برای زنجیره پروکسی یا اتصال کلاینت به سرور
        if mode in ['forward', 'client']:
            server_ip = config.get('server_ip', '')
            server_port = config.get('server_port', '')
            forward_proto = config.get('forward_proto', 'socks5') # wss, mwss, kcp, quic...
            
            # احراز هویت (User/Pass)
            auth = ""
            if config.get('user') and config.get('pass'):
                auth = f"{config['user']}:{config['pass']}@"
            
            args.append(f'-F="{forward_proto}://{auth}{server_ip}:{server_port}"')

        return " ".join(args)

    def install_server(self, server_ip, config):
        """نصب Gost روی سرور خارج"""
        logger.info(f"Installing Gost Server on {server_ip}")
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
            # 1. بررسی و نصب
            run("Check Connection", "whoami")
            run("Mkdir", "mkdir -p /root/alamor/bin")
            
            # دانلود و اکسترکت (فایل gz است)
            check_cmd = f"[ -f {REMOTE_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
            if "MISSING" in run("Check Binary", check_cmd):
                dl_cmd = f"curl -L -o /tmp/gost.gz {DOWNLOAD_URL} && gzip -d -f /tmp/gost.gz && mv /tmp/gost {REMOTE_BIN_PATH} && chmod +x {REMOTE_BIN_PATH}"
                run("Download Gost", dl_cmd)

            # 2. ساخت دستور اجرا
            # مود server معمولا فقط Listen میکند یا منتظر Reverse connection است
            gost_cmd = self._build_args('server', config)
            if config.get('raw_args'): # امکان ارسال دستور خام برای انعطاف بیشتر
                gost_cmd = config['raw_args']

            # 3. ساخت سرویس
            svc_content = f'''[Unit]
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
'''
            run("Create Service", f"cat <<EOF > /etc/systemd/system/gost.service\n{svc_content}\nEOF")

            # 4. استارت
            run("Start Service", "systemctl daemon-reload && systemctl restart gost && systemctl enable gost")

            return True, "Gost Server Installed Successfully"

        except Exception as e:
            logger.error(f"Server Install Error: {e}")
            return False, str(e)

    def install_client(self, server_ip, config):
        """نصب Gost روی کلاینت (ایران)"""
        logger.info("Installing Gost Client Locally")
        try:
            # 1. دانلود
            if not os.path.exists(LOCAL_BIN_PATH):
                os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
                subprocess.run(f"curl -L -o /tmp/gost.gz {DOWNLOAD_URL}", shell=True, check=True)
                subprocess.run("gzip -d -f /tmp/gost.gz", shell=True, check=True)
                subprocess.run(f"mv /tmp/gost {LOCAL_BIN_PATH}", shell=True, check=True)
                subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

            # 2. ساخت دستور اجرا
            config['server_ip'] = server_ip # افزودن آی‌پی سرور به کانفیگ
            gost_cmd = self._build_args('client', config)
            if config.get('raw_args'):
                gost_cmd = config['raw_args']

            # 3. سرویس
            svc_content = f'''[Unit]
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
'''
            with open("/etc/systemd/system/gost-client.service", "w") as f:
                f.write(svc_content)

            # 4. استارت
            os.system("systemctl daemon-reload")
            os.system("systemctl enable gost-client")
            os.system("systemctl restart gost-client")

            return True, "Gost Client Installed Successfully"

        except Exception as e:
            logger.error(f"Client Install Error: {e}")
            return False, str(e)