import os
import logging
import subprocess
from core.ssh_manager import SSHManager

# تنظیمات لاگ
logger = logging.getLogger("GostManager")
logger.setLevel(logging.INFO)

# ثابت‌ها
REMOTE_BIN_PATH = "/root/alamor/bin/gost"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/gost"
DOWNLOAD_URL = "https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz"

class GostManager:
    def __init__(self):
        pass

    def _build_args(self, mode, config):
        """
        ساخت آرگومان‌های خط فرمان Gost بر اساس داکیومنت و نیاز
        """
        args = []
        
        # -------------------------------------------
        # 1. Listen Node (-L)
        # -------------------------------------------
        # پروتکل: tcp, udp, socks5, http, rtcp, rudp, tls, ws, ...
        listen_proto = config.get('listen_proto', 'socks5') 
        
        # آی‌پی و پورت اتصال
        bind_ip = config.get('bind_ip', '') # خالی یعنی همه
        bind_port = config.get('bind_port', 1080)
        
        # تارگت (برای پورت فورواردینگ)
        # مثال: tcp://:2222/192.168.1.1:22 -> در اینجا 192... تارگت است
        target = f"/{config['target']}" if config.get('target') else ""
        
        # پارامترهای اضافی (مثل ?cert=... یا ?ttl=...)
        extras = config.get('extras', '')
        if extras and not extras.startswith('?'):
            extras = f"?{extras}"

        # ساخت رشته نهایی Listen
        # فرمت: -L="protocol://bind_ip:port/target?extras"
        args.append(f'-L="{listen_proto}://{bind_ip}:{bind_port}{target}{extras}"')

        # -------------------------------------------
        # 2. Forward Node (-F) - اختیاری
        # -------------------------------------------
        # برای اتصال کلاینت به سرور یا زنجیره پروکسی
        if mode in ['forward', 'client']:
            server_ip = config.get('server_ip', '')
            server_port = config.get('server_port', '')
            forward_proto = config.get('forward_proto', 'socks5') # wss, kcp, quic, ...
            
            # احراز هویت (User/Pass) در لینک فوروارد
            auth = ""
            if config.get('user') and config.get('pass'):
                auth = f"{config['user']}:{config['pass']}@"
            
            # ساخت رشته نهایی Forward
            # فرمت: -F="protocol://user:pass@server_ip:port"
            if server_ip and server_port:
                args.append(f'-F="{forward_proto}://{auth}{server_ip}:{server_port}"')

        return " ".join(args)

    def install_server(self, server_ip, config):
        """
        نصب و راه‌اندازی Gost روی سرور خارج (Remote)
        """
        logger.info(f"Installing Gost Server on {server_ip}...")
        
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
            # 1. بررسی اتصال و ساخت پوشه
            run("Check Connection", "whoami")
            run("Mkdir", "mkdir -p /root/alamor/bin")
            
            # 2. دانلود و نصب (اگر وجود نداشت)
            check_cmd = f"[ -f {REMOTE_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
            if "MISSING" in run("Check Binary", check_cmd):
                # دانلود فایل GZ، اکسترکت، تغییر نام و دسترسی اجرا
                dl_cmd = (
                    f"curl -L -o /tmp/gost.gz {DOWNLOAD_URL} && "
                    f"gzip -d -f /tmp/gost.gz && "
                    f"mv /tmp/gost {REMOTE_BIN_PATH} && "
                    f"chmod +x {REMOTE_BIN_PATH}"
                )
                run("Download Gost", dl_cmd)

            # 3. آماده‌سازی دستور اجرا
            # اگر کاربر دستور خام (Raw Args) داده باشد، اولویت با آن است
            # در غیر این صورت دستور با تابع _build_args ساخته می‌شود
            gost_cmd = config.get('gost_args') or self._build_args('server', config)

            # 4. ساخت فایل سرویس Systemd
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

            # 5. استارت سرویس
            run("Start Service", "systemctl daemon-reload && systemctl restart gost && systemctl enable gost")

            logger.info("Gost Server Installed Successfully")
            return True, "Gost Server Installed"

        except Exception as e:
            logger.error(f"Server Install Error: {e}")
            return False, str(e)

    def install_client(self, server_ip, config):
        """
        نصب و راه‌اندازی Gost روی کلاینت (سرور ایران) - Local
        """
        logger.info("Installing Gost Client Locally...")
        try:
            # 1. دانلود و نصب (اگر وجود نداشت)
            if not os.path.exists(LOCAL_BIN_PATH):
                os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
                subprocess.run(f"curl -L -o /tmp/gost.gz {DOWNLOAD_URL}", shell=True, check=True)
                subprocess.run("gzip -d -f /tmp/gost.gz", shell=True, check=True)
                subprocess.run(f"mv /tmp/gost {LOCAL_BIN_PATH}", shell=True, check=True)
                subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

            # 2. آماده‌سازی دستور اجرا
            config['server_ip'] = server_ip # اضافه کردن آی‌پی سرور برای بیلد کردن دستور
            gost_cmd = config.get('gost_args') or self._build_args('client', config)

            # 3. ساخت فایل سرویس Systemd لوکال
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

            # 4. استارت سرویس
            os.system("systemctl daemon-reload")
            os.system("systemctl enable gost-client")
            os.system("systemctl restart gost-client")

            logger.info("Gost Client Installed Successfully")
            return True, "Gost Client Installed"

        except Exception as e:
            logger.error(f"Client Install Error: {e}")
            return False, str(e)