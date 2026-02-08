import os
import yaml
import secrets
import logging
import subprocess
from core.ssh_manager import SSHManager

# تنظیم لاگ‌ها
LOG_DIR = '/root/AlamorTunnel/logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=f'{LOG_DIR}/install.log', 
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ثابت‌ها
REMOTE_BIN_PATH = "/root/alamor/bin/hysteria"
REMOTE_CONFIG_PATH = "/root/alamor/bin/config.yaml"
LOCAL_BIN_PATH = "/root/AlamorTunnel/bin/hysteria"
LOCAL_CONFIG_PATH = "/root/AlamorTunnel/bin/client.yaml"
STATS_PORT = 9999
HOP_RANGE = "20000:50000"

# ==========================================
# بخش ۱: توابع کمکی (Helper Functions)
# ==========================================

def generate_pass():
    """تولید رمز عبور امن ۱۶ رقمی"""
    return secrets.token_hex(16)

def generate_server_config(config):
    """تولید کانفیگ سرور (YAML)"""
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
        },
        "bandwidth": {
            "up": config.get('up_mbps', '100 mbps'),
            "down": config.get('down_mbps', '100 mbps')
        },
        "ignoreClientBandwidth": False
    }
    return yaml.dump(server_conf), stats_secret

# ==========================================
# بخش ۲: نصب سرور ریموت (خارج)
# ==========================================

def install_hysteria_server_remote(server_ip, config):
    logging.info(f"Starting Remote Install on {server_ip}")
    ssh = SSHManager()
    ssh_port = int(config.get('ssh_port', 22))
    ssh_pass = config.get('ssh_pass')

    def run(name, cmd):
        logging.info(f"STEP: {name}")
        ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, cmd, ssh_port)
        if not ok:
            logging.error(f"FAILED {name}: {out}")
            return False, f"Step '{name}' Failed: {out}"
        logging.info(f"SUCCESS {name}")
        return True, out

    # 1. تست اتصال
    if not run("Check Connection", "whoami")[0]: return False, "SSH Connection Failed"

    # 2. ساخت دایرکتوری‌ها
    run("Mkdir", "mkdir -p /root/alamor/bin /root/alamor/certs")
    
    # 3. نصب پیش‌نیازها
    deps_cmd = "export DEBIAN_FRONTEND=noninteractive; apt-get update -y && apt-get install -y iptables iptables-persistent openssl ca-certificates"
    if not run("Install Deps", deps_cmd)[0]: return False, "Dependency Installation Failed"

    # 4. ساخت سرتیفیکیت SSL
    cert_cmd = (
        "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 "
        "-subj '/CN=www.bing.com' "
        "-keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
    )
    if not run("Generate Cert", cert_cmd)[0]: return False, "Certificate Generation Failed"

    # 5. دانلود هسته هیستریا
    dl_cmd = (
        f"curl -L -k -o {REMOTE_BIN_PATH} "
        "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 "
        f"&& chmod +x {REMOTE_BIN_PATH}"
    )
    if not run("Download Core", dl_cmd)[0]: return False, "Core Download Failed"

    # 6. نوشتن فایل کانفیگ
    yaml_content, stats_secret = generate_server_config(config)
    config['stats_secret'] = stats_secret
    
    write_cmd = f"cat <<EOF > {REMOTE_CONFIG_PATH}\n{yaml_content}\nEOF"
    if not run("Write Config", write_cmd)[0]: return False, "Config Write Failed"

    # 7. تنظیم فایروال (Port Hopping)
    tunnel_port = config['tunnel_port']
    fw_cmd = (
        f"iptables -t nat -F PREROUTING; "
        f"iptables -t nat -A PREROUTING -p udp --dport {HOP_RANGE} -j REDIRECT --to-ports {tunnel_port}; "
        "netfilter-persistent save || true"
    )
    run("Firewall", fw_cmd)

    # 8. ساخت فایل سرویس
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
    run("Service File", svc_cmd)

    # 9. استارت سرویس
    ok, msg = run("Start", "systemctl daemon-reload && systemctl restart hysteria-server && systemctl is-active hysteria-server")
    
    if "active" in msg or "running" in msg:
        return True, "Installation Successful"
    return False, f"Service Failed to Start: {msg}"

# ==========================================
# بخش ۳: نصب کلاینت لوکال (ایران)
# ==========================================

def install_hysteria_client_local(server_ip, config):
    """
    نصب و تنظیم نسخه کلاینت روی سرور ایران (برای حل ارور Import)
    """
    logging.info("Starting Local Client Install")
    try:
        # 1. دانلود هسته اگر وجود نداشت
        if not os.path.exists(LOCAL_BIN_PATH):
            os.makedirs(os.path.dirname(LOCAL_BIN_PATH), exist_ok=True)
            subprocess.run(f"curl -L -k -o {LOCAL_BIN_PATH} https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64", shell=True, check=True)
            subprocess.run(f"chmod +x {LOCAL_BIN_PATH}", shell=True, check=True)

        # 2. تولید کانفیگ کلاینت
        client_conf = {
            "server": f"{server_ip}:{HOP_RANGE}",
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
                "listen": "0.0.0.0:1080"
            },
            "http": {
                "listen": "0.0.0.0:8080"
            }
        }
        
        # پورت فورواردینگ (اختیاری)
        if 'ports' in config and config['ports']:
            tcp_fw = []
            udp_fw = []
            # تبدیل رشته پورت‌ها به لیست
            ports = str(config['ports']).split(',') if isinstance(config['ports'], str) else config['ports']
            
            for p in ports:
                p = str(p).strip()
                if p:
                    tcp_fw.append({"listen": f"0.0.0.0:{p}", "remote": f"127.0.0.1:{p}"})
                    udp_fw.append({"listen": f"0.0.0.0:{p}", "remote": f"127.0.0.1:{p}", "timeout": "60s"})
            
            client_conf['tcpForwarding'] = tcp_fw
            client_conf['udpForwarding'] = udp_fw

        # ذخیره کانفیگ
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

[Install]
WantedBy=multi-user.target
"""
        with open("/etc/systemd/system/hysteria-client.service", "w") as f:
            f.write(svc_content)

        # 4. استارت سرویس
        os.system("systemctl daemon-reload")
        os.system("systemctl enable hysteria-client")
        os.system("systemctl restart hysteria-client")
        
        logging.info("Local Client Installed Successfully")
        return True, "Client Installed Successfully"

    except Exception as e:
        logging.error(f"Local Install Error: {e}")
        return False, f"Local Install Error: {str(e)}"