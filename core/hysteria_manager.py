import os
import yaml
import secrets
import time
from core.ssh_manager import SSHManager

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
        "resolver": {
            "type": "udp",
            "udp": {
                "addr": "8.8.8.8:53",
                "timeout": "4s"
            }
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
    ssh = SSHManager()
    ssh_port = int(config.get('ssh_port', 22))
    ssh_pass = config.get('ssh_pass')

    if not ssh_pass:
        return False, "SSH Password missing in config"

    # تابع کمکی برای اجرای دستور و لاگ کردن خطا
    def run_step(name, cmd):
        # اضافه کردن timeout برای جلوگیری از هنگ کردن
        full_cmd = f"timeout 120 bash -c '{cmd}'" 
        ok, out = ssh.run_remote_command(server_ip, "root", ssh_pass, full_cmd, ssh_port)
        if not ok:
            return False, f"{name} Failed: {out}"
        return True, out

    # 1. تست اتصال و ساخت پوشه‌ها
    ok, msg = run_step("Init", "mkdir -p /root/alamor/bin /root/alamor/certs && echo 'OK'")
    if not ok: return False, msg

    # 2. نصب پیش‌نیازها (فقط اگر نیاز باشد)
    # ترفند: استفاده از DEBIAN_FRONTEND=noninteractive قبل از apt
    install_cmd = (
        "export DEBIAN_FRONTEND=noninteractive; "
        "if ! command -v iptables &> /dev/null; then "
        "apt-get update -qq && apt-get install -y -qq iptables iptables-persistent; "
        "fi; "
        "sysctl -w net.ipv4.ip_forward=1"
    )
    ok, msg = run_step("Dependencies", install_cmd)
    if not ok: return False, msg # اگر اینجا ارور داد، لاگ دقیق برمیگرداند

    # 3. سرتیفیکیت
    cert_cmd = (
        "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 "
        f"-subj '/CN=www.bing.com' "
        "-keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
    )
    ok, msg = run_step("Certificate", cert_cmd)
    if not ok: return False, msg

    # 4. دانلود باینری (هوشمند)
    # چک میکنیم اگر فایل هست و سالمه، دانلود نکنیم
    check_cmd = f"[ -f {HYSTERIA_BIN_PATH} ] && echo 'EXISTS' || echo 'MISSING'"
    _, check_out = run_step("Check Bin", check_cmd)
    
    if "MISSING" in check_out:
        dl_cmd = (
            f"curl -L --retry 3 --max-time 60 -o {HYSTERIA_BIN_PATH} "
            "https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 "
            f"&& chmod +x {HYSTERIA_BIN_PATH}"
        )
        ok, msg = run_step("Download Core", dl_cmd)
        if not ok: return False, msg

    # 5. کانفیگ
    yaml_content, stats_secret = generate_server_config(config)
    config['stats_secret'] = stats_secret 
    # نوشتن فایل با echo و base64 برای جلوگیری از کاراکترهای عجیب
    # (اما اینجا ساده می‌نویسیم چون yaml معمولا امن است)
    create_conf_cmd = f"cat <<EOF > {SERVER_CONFIG_PATH}\n{yaml_content}\nEOF"
    ok, msg = run_step("Write Config", create_conf_cmd)
    if not ok: return False, msg

    # 6. Iptables (Port Hopping)
    tunnel_port = config['tunnel_port']
    ipt_cmd = (
        f"iptables -t nat -D PREROUTING -p udp --dport {HOP_RANGE.replace(':','-')} -j REDIRECT --to-ports {tunnel_port} 2>/dev/null || true; "
        f"iptables -t nat -A PREROUTING -p udp --dport {HOP_RANGE} -j REDIRECT --to-ports {tunnel_port}; "
        "netfilter-persistent save 2>/dev/null || true; "
        f"ufw allow {tunnel_port}/udp 2>/dev/null || true; "
        f"ufw allow {tunnel_port}/tcp 2>/dev/null || true; "
        f"ufw allow {HOP_RANGE}/udp 2>/dev/null || true"
    )
    ok, msg = run_step("Firewall", ipt_cmd)
    if not ok: return False, msg

    # 7. سرویس Systemd
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

    # 8. استارت
    start_cmd = "systemctl daemon-reload && systemctl enable hysteria-server && systemctl restart hysteria-server"
    return run_step("Start Service", start_cmd)

def install_hysteria_client_local(server_ip, config):
    local_bin = "/root/AlamorTunnel/bin/hysteria"
    if not os.path.exists(local_bin):
        os.system(f"mkdir -p /root/AlamorTunnel/bin")
        os.system(f"curl -L -o {local_bin} https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64")
        os.system(f"chmod +x {local_bin}")

    hopping_addr = f"{server_ip}:{HOP_RANGE}"
    
    client_conf = {
        "server": hopping_addr,
        "auth": config['password'],
        "tls": {
            "sni": "www.bing.com",
            "insecure": True
        },
        "transport": {
            "type": "udp",
            "udp": {
                "hopInterval": "30s"
            }
        },
        "bandwidth": {
            "up": config.get('up_mbps', '100 mbps'),
            "down": config.get('down_mbps', '100 mbps')
        },
        "socks5": {"listen": "127.0.0.1:1080"},
        "http": {"listen": "127.0.0.1:8080"}
    }
    
    if 'ports' in config and config['ports']:
        tcp_fw = []
        udp_fw = []
        for p in config['ports']:
            tcp_fw.append({"listen": f"0.0.0.0:{p}", "remote": f"127.0.0.1:{p}"})
            udp_fw.append({"listen": f"0.0.0.0:{p}", "remote": f"127.0.0.1:{p}", "timeout": "60s"})
        client_conf['tcpForwarding'] = tcp_fw
        client_conf['udpForwarding'] = udp_fw

    with open(CLIENT_CONFIG_PATH, 'w') as f:
        yaml.dump(client_conf, f)

    service_file = f"""[Unit]
Description=Hysteria Client
After=network.target

[Service]
Type=simple
ExecStart={local_bin} client -c {CLIENT_CONFIG_PATH}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    with open("/etc/systemd/system/hysteria-client.service", "w") as f:
        f.write(service_file)

    os.system("systemctl daemon-reload && systemctl enable hysteria-client && systemctl restart hysteria-client")
    return True