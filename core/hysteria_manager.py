import os
import yaml
import secrets
import logging
import subprocess
from core.ssh_manager import SSHManager

# تنظیمات لاگ (برای عیب‌یابی دقیق)
LOG_DIR = '/root/AlamorTunnel/logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("HysteriaManager")
file_handler = logging.FileHandler(f'{LOG_DIR}/hysteria_install.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

# ثابت‌ها و مسیرها
REMOTE_BIN_PATH = "/root/alamor/bin/hysteria"
REMOTE_CONFIG_PATH = "/root/alamor/bin/config.yaml"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/hysteria"
LOCAL_CONFIG_PATH = "/root/AlamorTunnel/bin/client.yaml"
DOWNLOAD_URL = "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64"
STATS_PORT = 9999
HOP_RANGE = "20000:50000"

# ==========================================
# بخش ۱: توابع کمکی (Helper Functions)
# ==========================================

def generate_pass():
    """تولید رمز عبور امن ۱۶ رقمی برای تانل"""
    return secrets.token_hex(16)

def generate_server_config(config):
    """
    تولید کانفیگ YAML برای سرور Hysteria v2
    """
    stats_secret = secrets.token_hex(8)
    
    # ساختار استاندارد کانفیگ Hysteria 2
    server_conf = {
        "listen": f":{config['tunnel_port']}",
        "tls": {
            "cert": "/root/alamor/certs/server.crt",
            "key": "/root/alamor/certs/server.key"
        },
        "auth": {
            "type": "password",
            "password": config['password']
        },
        "masquerade": {
            "type": "proxy",
            "proxy": {
                "url": "https://www.bing.com",
                "rewriteHost": True
            }
        },
        "trafficStats": {
            "listen": f"127.0.0.1:{STATS_PORT}",
            "secret": stats_secret
        },
        "acl": {
            "inline": [
                "reject(geoip:cn)", 
                "reject(geoip:ir)",
                "reject(geosite:category-ads-all)"
            ]
        },
        "bandwidth": {
            "up": config.get('up_mbps', '100 mbps'),
            "down": config.get('down_mbps', '100 mbps')
        },
        "ignoreClientBandwidth": False,
        "disableUDP": False,
        "udpIdleTimeout": "60s"
    }
    return yaml.dump(server_conf), stats_secret

# ==========================================
# بخش ۲: نصب سرور ریموت (خارج)
# ==========================================

def install_hysteria_server_remote(server_ip, config):
    """
    نصب کامل Hysteria روی سرور خارج از طریق SSH
    """
    logger.info(f"Starting Remote Installation on {server_ip}")
    ssh = SSHManager()
    ssh_port = int(config.get('ssh_port', 22))
    ssh_pass = config.get('ssh_pass')

    # تابع داخلی برای اجرای تمیز دستورات
    def run_step(step_name, cmd):
        logger.info(f"STEP: {step_name}")
        ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port)
        if not ok:
            logger.error(f"FAILED {step_name}: {out}")
            return False, f"Step '{step_name}' Failed: {out}"
        return True, out

    try:
        # 1. تست اتصال SSH
        if not run_step("Check Connection", "whoami")[0]: 
            return False, "SSH Connection Failed. Check IP/Pass/Port."

        # 2. ساخت دایرکتوری‌های مورد نیاز
        run_step("Create Directories", "mkdir -p /root/alamor/bin /root/alamor/certs")
        
        # 3. نصب پیش‌نیازها (بدون گیر کردن روی apt)
        deps_cmd = "export DEBIAN_FRONTEND=noninteractive; apt-get update -y && apt-get install -y iptables iptables-persistent openssl ca-certificates curl"
        if not run_step("Install Dependencies", deps_cmd)[0]: 
            return False, "Dependency Installation Failed"

        # 4. تولید سرتیفیکیت Self-Signed
        cert_cmd = (
            "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 "
            "-subj '/CN=www.bing.com' "
            "-keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
        )
        if not run_step("Generate Certificates", cert_cmd)[0]: 
            return False, "Certificate Generation Failed"

        # 5. دانلود هسته Hysteria (اگر وجود ندارد یا آپدیت نیاز است)
        # از فلگ -k برای نادیده گرفتن خطاهای SSL در سرورهای قدیمی استفاده می‌کنیم
        dl_cmd = (
            f"curl -L -k -o {REMOTE_BIN_PATH} {DOWNLOAD_URL} "
            f"&& chmod +x {REMOTE_BIN_PATH}"
        )
        if not run_step("Download Core", dl_cmd)[0]: 
            return False, "Core Download Failed"

        # 6. تولید و آپلود کانفیگ
        yaml_content, stats_secret = generate_server_config(config)
        config['stats_secret'] = stats_secret # ذخیره برای استفاده‌های بعدی
        
        write_cmd = f"cat <<EOF > {REMOTE_CONFIG_PATH}\n{yaml_content}\nEOF"
        if not run_step("Write Config", write_cmd)[0]: 
            return False, "Config Write Failed"

        # 7. تنظیم فایروال (Port Hopping)
        # تمام پورت‌های رنج HOP_RANGE را به پورت اصلی تانل هدایت می‌کنیم
        tunnel_port = config['tunnel_port']
        fw_cmd = (
            f"iptables -t nat -F PREROUTING; "
            f"iptables -t nat -A PREROUTING -p udp --dport {HOP_RANGE} -j REDIRECT --to-ports {tunnel_port}; "
            "netfilter-persistent save || true"
        )
        run_step("Setup Firewall", fw_cmd)

        # 8. ساخت فایل سرویس Systemd
        svc_content = f"""[Unit]
Description=Hysteria 2 Server
After=network.target

[Service]
Type=simple
ExecStart={REMOTE_BIN_PATH} server -c {REMOTE_CONFIG_PATH}
WorkingDirectory=/root/alamor/bin
User=root
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
        svc_cmd = f"cat <<EOF > /etc/systemd/system/hysteria-server.service\n{svc_content}\nEOF"
        run_step("Create Service File", svc_cmd)

        # 9. استارت و فعال‌سازی سرویس
        start_cmd = "systemctl daemon-reload && systemctl enable hysteria-server && systemctl restart hysteria-server && systemctl is-active hysteria-server"
        ok, msg = run_step("Start Service", start_cmd)
        
        if ok and ("active" in msg or "running" in msg):
            return True, "Hysteria Server Installed Successfully"
        
        return False, f"Service Failed to Start. Status: {msg}"

    except Exception as e:
        logger.error(f"Critical Error in Remote Install: {e}")
        return False, str(e)

# ==========================================
# بخش ۳: نصب کلاینت لوکال (ایران)
# ==========================================

def install_hysteria_client_local(server_ip, config):
    """
    نصب کلاینت روی سرور ایران برای برقراری ارتباط با خارج
    """
    logger.info("Starting Local Client Installation")
    try:
        # 1. دانلود هسته اگر وجود نداشت
        if not os.path.exists(LOCAL_BIN_PATH):
            logger.info("Downloading Local Binary...")
            os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
            subprocess.run(f"curl -L -k -o {LOCAL_BIN_PATH} {DOWNLOAD_URL}", shell=True, check=True)
            subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

        # 2. تولید کانفیگ کلاینت
        client_conf = {
            "server": f"{server_ip}:{HOP_RANGE}", # استفاده از پورت هوپینگ برای اتصال
            "auth": config['password'],
            "tls": {
                "sni": "www.bing.com",
                "insecure": True
            },
            "bandwidth": {
                "up": config.get('up_mbps', '100 mbps'),
                "down": config.get('down_mbps', '100 mbps')
            },
            "socks5": {
                "listen": "0.0.0.0:1080" # پورت ساکس پیش‌فرض
            },
            "http": {
                "listen": "0.0.0.0:8080" # پورت HTTP پیش‌فرض
            },
            "transport": {
                "type": "udp",
                "udp": {
                    "hopInterval": "30s" # تغییر پورت هر 30 ثانیه
                }
            }
        }
        
        # مدیریت پورت فورواردینگ (در صورت وجود)
        if 'ports' in config and config['ports']:
            tcp_fw = []
            udp_fw = []
            # تبدیل ورودی به لیست (چه رشته باشد چه لیست)
            ports = str(config['ports']).split(',') if isinstance(config['ports'], str) else config['ports']
            
            for p in ports:
                p = str(p).strip()
                if p:
                    # گوش دادن روی تمام اینترفیس‌ها (0.0.0.0) و ارسال به لوکال هاست
                    tcp_fw.append({"listen": f"0.0.0.0:{p}", "remote": f"127.0.0.1:{p}"})
                    udp_fw.append({"listen": f"0.0.0.0:{p}", "remote": f"127.0.0.1:{p}", "timeout": "60s"})
            
            client_conf['tcpForwarding'] = tcp_fw
            client_conf['udpForwarding'] = udp_fw

        # ذخیره فایل کانفیگ
        with open(LOCAL_CONFIG_PATH, 'w') as f:
            yaml.dump(client_conf, f)

        # 3. ساخت سرویس کلاینت
        svc_content = f"""[Unit]
Description=Hysteria Client (Iran)
After=network.target

[Service]
Type=simple
ExecStart={LOCAL_BIN_PATH} client -c {LOCAL_CONFIG_PATH}
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
        with open("/etc/systemd/system/hysteria-client.service", "w") as f:
            f.write(svc_content)

        # 4. استارت سرویس لوکال
        os.system("systemctl daemon-reload")
        os.system("systemctl enable hysteria-client")
        os.system("systemctl restart hysteria-client")
        
        logger.info("Local Client Installed Successfully")
        return True, "Client Installed Successfully"

    except subprocess.CalledProcessError as e:
        logger.error(f"Local Download Failed: {e}")
        return False, "Failed to download Hysteria binary locally."
    except Exception as e:
        logger.error(f"Local Install Error: {e}")
        return False, f"Local Install Error: {str(e)}"