import os
import yaml
import secrets
import logging
from core.ssh_manager import SSHManager

# تنظیم لاگ
logging.basicConfig(filename='/root/AlamorTunnel/install_debug.log', level=logging.DEBUG, format='%(asctime)s %(message)s')

# --- CONSTANTS ---
HYSTERIA_BIN_PATH = "/root/alamor/bin/hysteria"
SERVER_CONFIG_PATH = "/root/alamor/bin/config.yaml"
STATS_PORT = 9999
HOP_RANGE = "20000:50000"

def generate_server_config(config):
    stats_secret = secrets.token_hex(8)
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
            "inline": ["reject(geoip:cn)", "reject(geoip:ir)"]
        }
    }
    return yaml.dump(server_conf), stats_secret

def install_hysteria_server_remote(server_ip, config):
    ssh = SSHManager()
    ssh_port = int(config.get('ssh_port', 22))
    ssh_pass = config.get('ssh_pass')

    # تابع اجرای دستور (ساده و بدون پیچیدگی)
    def run(name, cmd):
        logging.info(f"CMD [{name}]: {cmd}")
        ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port)
        if not ok:
            logging.error(f"FAIL [{name}]: {out}")
            # اینجا ارور دقیق را برمی‌گرداند
            return False, f"Step '{name}' Failed: {out}"
        logging.info(f"OK [{name}]: {out[:50]}...")
        return True, out

    # 1. تست اتصال (ساده‌ترین دستور ممکن)
    ok, msg = run("Check Connection", "whoami")
    if not ok: return False, msg

    # 2. ساخت پوشه‌ها
    run("Mkdir", "mkdir -p /root/alamor/bin /root/alamor/certs")

    # 3. نصب پیش‌نیازها
    # استفاده از DEBIAN_FRONTEND برای جلوگیری از گیر کردن apt
    apt_cmd = "export DEBIAN_FRONTEND=noninteractive; apt-get update -y && apt-get install -y iptables iptables-persistent openssl"
    ok, msg = run("Install Deps", apt_cmd)
    if not ok: return False, msg

    # 4. ساخت سرتیفیکیت
    cert_cmd = (
        "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 "
        "-subj '/CN=www.bing.com' "
        "-keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
    )
    ok, msg = run("Generate Cert", cert_cmd)
    if not ok: return False, msg

    # 5. دانلود هسته
    dl_cmd = (
        f"curl -L -k -o {HYSTERIA_BIN_PATH} "
        "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 "
        f"&& chmod +x {HYSTERIA_BIN_PATH}"
    )
    ok, msg = run("Download Core", dl_cmd)
    if not ok: return False, msg

    # 6. کانفیگ
    yaml_content, stats_secret = generate_server_config(config)
    config['stats_secret'] = stats_secret
    
    # نوشتن کانفیگ
    write_cmd = f"cat <<EOF > {SERVER_CONFIG_PATH}\n{yaml_content}\nEOF"
    ok, msg = run("Write Config", write_cmd)
    if not ok: return False, msg

    # 7. فایروال
    tunnel_port = config['tunnel_port']
    fw_cmd = (
        f"iptables -t nat -A PREROUTING -p udp --dport {HOP_RANGE} -j REDIRECT --to-ports {tunnel_port}; "
        "netfilter-persistent save || true"
    )
    run("Firewall", fw_cmd)

    # 8. فایل سرویس
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

[Install]
WantedBy=multi-user.target
"""
    svc_cmd = f"cat <<EOF > /etc/systemd/system/hysteria-server.service\n{svc_content}\nEOF"
    run("Service File", svc_cmd)

    # 9. استارت
    ok, msg = run("Start", "systemctl daemon-reload && systemctl restart hysteria-server && systemctl is-active hysteria-server")
    
    if "active" in msg or "running" in msg:
        return True, "Installation Successful"
    else:
        return False, f"Service status error: {msg}"