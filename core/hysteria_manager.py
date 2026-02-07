import os
import yaml
import secrets
import time
import logging
import traceback
from core.ssh_manager import SSHManager

# --- LOGGING SETUP ---
LOG_FILE = "/root/AlamorTunnel/install_debug.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w' # هر بار فایل را خالی کن و از اول بنویس
)

# --- CONSTANTS ---
HYSTERIA_BIN_PATH = "/root/alamor/bin/hysteria"
SERVER_CONFIG_PATH = "/root/alamor/bin/config.yaml"
CLIENT_CONFIG_PATH = "/root/AlamorTunnel/bin/hysteria_client.yaml"
STATS_PORT = 9999
HOP_RANGE = "20000:50000"

def generate_pass():
    return secrets.token_hex(16)

def generate_server_config(config):
    stats_secret = config.get('stats_secret', secrets.token_hex(8))
    
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
                "url": config.get('masq_url', 'https://www.bing.com'),
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
        "ignoreClientBandwidth": False
    }
    return yaml.dump(server_conf), stats_secret

def install_hysteria_server_remote(server_ip, config):
    logging.info(f"--- STARTING INSTALLATION ON {server_ip} ---")
    
    try:
        ssh = SSHManager()
        ssh_port = int(config.get('ssh_port', 22))
        ssh_pass = config.get('ssh_pass')

        if not ssh_pass:
            logging.error("SSH Password missing")
            return False, "SSH Password missing in config"

        # تابع کمکی برای اجرای دستور و لاگ کردن
        def run_step(name, cmd):
            logging.info(f"STEP: {name} | CMD: {cmd}")
            
            # اضافه کردن 2>&1 برای گرفتن تمام ارورها
            # اضافه کردن timeout
            full_cmd = f"timeout 120 bash -c '{cmd}' 2>&1"
            
            try:
                ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, full_cmd, ssh_port)
            except Exception as e:
                logging.error(f"SSH Exception in {name}: {str(e)}")
                return False, f"SSH Exception: {str(e)}"

            if not ok:
                logging.error(f"FAILED: {name} | OUTPUT: {out}")
                return False, f"{name} Failed: {out}"
            
            logging.info(f"SUCCESS: {name} | OUTPUT: {out[:100]}...") # لاگ کردن بخشی از خروجی
            return True, out

        # 0. تست اتصال ساده
        logging.info("Testing SSH Connection...")
        ok, msg = run_step("SSH Connectivity Test", "echo 'Connection Established'")
        if not ok: return False, f"Could not connect to server: {msg}"

        # 1. ساخت پوشه‌ها
        ok, msg = run_step("Init Directories", "mkdir -p /root/alamor/bin /root/alamor/certs")
        if not ok: return False, msg

        # 2. نصب پیش‌نیازها
        # چک میکنیم اگر پکیج‌ها نصب هستند، دوباره apt update نزنیم (صرفه‌جویی در زمان و کاهش ریسک)
        install_cmd = (
            "export DEBIAN_FRONTEND=noninteractive; "
            "if ! command -v iptables &> /dev/null; then "
            "   apt-get update -qq && apt-get install -y -qq iptables iptables-persistent; "
            "fi; "
            "if ! command -v openssl &> /dev/null; then "
            "   apt-get install -y -qq openssl; "
            "fi; "
            "sysctl -w net.ipv4.ip_forward=1"
        )
        ok, msg = run_step("Dependencies", install_cmd)
        if not ok: return False, msg

        # 3. سرتیفیکیت
        # اگر فایل وجود دارد، دوباره نساز
        cert_cmd = (
            "if [ ! -f /root/alamor/certs/server.key ]; then "
            "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 "
            "-subj '/CN=www.bing.com' "
            "-keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt; "
            "fi"
        )
        ok, msg = run_step("Certificate", cert_cmd)
        if not ok: return False, msg

        # 4. دانلود باینری
        dl_cmd = (
            f"if [ ! -f {HYSTERIA_BIN_PATH} ]; then "
            f"curl -L --retry 3 --max-time 60 -o {HYSTERIA_BIN_PATH} "
            "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 "
            f"&& chmod +x {HYSTERIA_BIN_PATH}; "
            "fi"
        )
        ok, msg = run_step("Download Core", dl_cmd)
        if not ok: return False, msg

        # 5. کانفیگ
        yaml_content, stats_secret = generate_server_config(config)
        config['stats_secret'] = stats_secret 
        
        # نوشتن فایل کانفیگ به روش امن‌تر
        # اول فایل را پاک میکنیم بعد مینویسیم
        create_conf_cmd = f"rm -f {SERVER_CONFIG_PATH} && cat <<EOF > {SERVER_CONFIG_PATH}\n{yaml_content}\nEOF"
        ok, msg = run_step("Write Config", create_conf_cmd)
        if not ok: return False, msg

        # 6. فایروال (پورت هاپینگ)
        tunnel_port = config['tunnel_port']
        ipt_cmd = (
            f"iptables -t nat -F PREROUTING; "  # پاک کردن رول‌های قبلی برای جلوگیری از تداخل
            f"iptables -t nat -A PREROUTING -p udp --dport {HOP_RANGE} -j REDIRECT --to-ports {tunnel_port}; "
            "netfilter-persistent save 2>/dev/null || true"
        )
        ok, msg = run_step("Firewall Rules", ipt_cmd)
        if not ok: return False, msg

        # 7. سرویس سیستم
        svc_content = f"""[Unit]
Description=Hysteria 2 Server
After=network.target

[Service]
Type=simple
ExecStart={HYSTERIA_BIN_PATH} server -c {SERVER_CONFIG_PATH}
WorkingDirectory=/root/alamor/bin
User=root
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
"""
        create_svc_cmd = f"cat <<EOF > /etc/systemd/system/hysteria-server.service\n{svc_content}\nEOF"
        ok, msg = run_step("Service File", create_svc_cmd)
        if not ok: return False, msg

        # 8. استارت سرویس
        start_cmd = (
            "systemctl daemon-reload && "
            "systemctl enable hysteria-server && "
            "systemctl restart hysteria-server && "
            "systemctl is-active hysteria-server" # چک کردن اینکه واقعا ران شده یا نه
        )
        ok, msg = run_step("Start Service", start_cmd)
        if not ok: return False, msg
        
        if "active" not in msg and "running" not in msg:
             return False, f"Service started but status is: {msg}"

        logging.info("Installation Completed Successfully")
        return True, "Installation Successful"

    except Exception as e:
        error_trace = traceback.format_exc()
        logging.critical(f"CRITICAL PYTHON ERROR:\n{error_trace}")
        return False, f"Python Script Error: {str(e)}"