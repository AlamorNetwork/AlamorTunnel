import os
import yaml
import secrets
from core.ssh_manager import SSHManager

# --- CONSTANTS ---
HYSTERIA_BIN_PATH = "/root/alamor/bin/hysteria"
SERVER_CONFIG_PATH = "/root/alamor/bin/config.yaml"
CLIENT_CONFIG_PATH = "/root/AlamorTunnel/bin/hysteria_client.yaml"
STATS_PORT = 9999  # پورت داخلی برای گرفتن آمار مصرف
HOP_RANGE = "20000:50000" # بازه پورت هاپینگ

def generate_pass():
    return secrets.token_hex(16)

def generate_server_config(config):
    """
    تولید کانفیگ سرور با قابلیت‌های پیشرفته:
    1. Traffic Stats برای مانیتورینگ
    2. Masquerade برای مخفی‌سازی
    3. ACL برای بستن سایت‌های ایرانی/چینی
    4. Resolver برای پایداری DNS
    """
    # تولید رمز API برای امنیت آمارگیری
    stats_secret = config.get('stats_secret', secrets.token_hex(8))
    
    server_conf = {
        "listen": f":{config['tunnel_port']}",
        
        # تنظیمات سرتیفیکیت (Self-Signed)
        "tls": {
            "cert": "/root/alamor/certs/server.crt",
            "key": "/root/alamor/certs/server.key"
        },
        
        # احراز هویت
        "auth": {
            "type": "password",
            "password": config['password']
        },
        
        # مخفی‌سازی ترافیک (شبیه سازی سایت واقعی)
        "masquerade": {
            "type": "proxy",
            "proxy": {
                "url": config.get('masq_url', 'https://www.bing.com'), # سایت هدف برای جعل
                "rewriteHost": True
            }
        },
        
        # فعال‌سازی API برای مانیتورینگ مصرف در پنل
        "trafficStats": {
            "listen": f"127.0.0.1:{STATS_PORT}",
            "secret": stats_secret
        },
        
        # تنظیمات DNS برای جلوگیری از نشتی
        "resolver": {
            "type": "udp",
            "udp": {
                "addr": "8.8.8.8:53",
                "timeout": "4s"
            }
        },
        
        # لیست سیاه (ACL) - مسدودسازی تبلیغات و IPهای مزاحم
        "acl": {
            "inline": [
                "reject(geoip:cn)",  # بلاک چین
                "reject(geoip:ir)",  # بلاک ایران (اختیاری - جلوگیری از لوپ)
                "reject(geosite:category-ads-all)" # بلاک تبلیغات
            ]
        },
        
        # تنظیمات پیشرفته پهنای باند (Brutal)
        "bandwidth": {
            "up": config.get('up_mbps', '100 mbps'),
            "down": config.get('down_mbps', '100 mbps')
        },
        "ignoreClientBandwidth": False # اجازه به کلاینت برای درخواست سرعت
    }
    
    # اگر پورت هاپینگ فعال بود، پورت اصلی را مخفی نمی‌کنیم اما iptables آن را فوروارد می‌کند
    
    return yaml.dump(server_conf), stats_secret

def install_hysteria_server_remote(server_ip, config):
    """
    نصب کامل در سرور خارج به همراه تنظیمات Iptables برای Port Hopping
    """
    ssh = SSHManager()
    
    # 1. آماده‌سازی محیط
    setup_cmds = [
        "mkdir -p /root/alamor/bin",
        "mkdir -p /root/alamor/certs",
        "pkill -f hysteria-server || true"  # توقف سرویس قبلی
    ]
    ssh.run_remote_command(server_ip, "root", config['ssh_pass'], "; ".join(setup_cmds), config['ssh_port'])

    # 2. تولید و آپلود سرتیفیکیت (Self-Signed)
    # نکته: هیستریا ۲ نیاز به سرتیفیکیت معتبر یا سلف-ساین قوی دارد
    cert_cmd = (
        "openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 "
        f"-subj '/C=US/ST=California/L=SanFrancisco/O=Alamor/CN={server_ip}' "
        "-keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt"
    )
    ssh.run_remote_command(server_ip, "root", config['ssh_pass'], cert_cmd, config['ssh_port'])

    # 3. دانلود باینری (اگر وجود ندارد)
    check_bin = f"test -f {HYSTERIA_BIN_PATH} && echo 'exists' || echo 'missing'"
    status, output = ssh.run_remote_command(server_ip, "root", config['ssh_pass'], check_bin, config['ssh_port'])
    
    if "missing" in output:
        # دانلود آخرین نسخه (لینک رسمی)
        download_cmd = f"curl -L -o {HYSTERIA_BIN_PATH} https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64 && chmod +x {HYSTERIA_BIN_PATH}"
        ssh.run_remote_command(server_ip, "root", config['ssh_pass'], download_cmd, config['ssh_port'])

    # 4. تولید و آپلود کانفیگ
    yaml_content, stats_secret = generate_server_config(config)
    # ذخیره Secret در کانفیگ ورودی برای استفاده‌های بعدی (مثلا ذخیره در دیتابیس)
    config['stats_secret'] = stats_secret 
    
    # نوشتن فایل کانفیگ در سرور
    create_conf_cmd = f"cat <<EOF > {SERVER_CONFIG_PATH}\n{yaml_content}\nEOF"
    ssh.run_remote_command(server_ip, "root", config['ssh_pass'], create_conf_cmd, config['ssh_port'])

    # 5. تنظیمات Port Hopping (مهم طبق داکیومنت)
    # ترافیک بازه ۲۰۰۰۰ تا ۵۰۰۰۰ را می‌فرستیم به پورت تانل
    tunnel_port = config['tunnel_port']
    iptables_cmds = [
        # فعال‌سازی IP Forwarding
        "sysctl -w net.ipv4.ip_forward=1",
        # پاک کردن رول‌های قبلی مربوط به هیستریا
        "iptables -t nat -D PREROUTING -p udp --dport 20000:50000 -j REDIRECT --to-ports 443 2>/dev/null || true",
        # اضافه کردن رول جدید
        f"iptables -t nat -A PREROUTING -p udp --dport {HOP_RANGE} -j REDIRECT --to-ports {tunnel_port}",
        # باز کردن پورت‌ها در فایروال
        f"ufw allow {tunnel_port}/udp",
        f"ufw allow {tunnel_port}/tcp",
        f"ufw allow {HOP_RANGE}/udp"
    ]
    ssh.run_remote_command(server_ip, "root", config['ssh_pass'], "; ".join(iptables_cmds), config['ssh_port'])

    # 6. ساخت سرویس Systemd
    service_file = f"""[Unit]
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
    create_svc_cmd = f"cat <<EOF > /etc/systemd/system/hysteria-server.service\n{service_file}\nEOF"
    ssh.run_remote_command(server_ip, "root", config['ssh_pass'], create_svc_cmd, config['ssh_port'])

    # 7. استارت سرویس
    start_cmd = "systemctl daemon-reload && systemctl enable hysteria-server && systemctl restart hysteria-server"
    success, msg = ssh.run_remote_command(server_ip, "root", config['ssh_pass'], start_cmd, config['ssh_port'])
    
    return success, msg

def install_hysteria_client_local(server_ip, config):
    """
    نصب و تنظیم کلاینت روی سرور ایران
    """
    # 1. دانلود باینری لوکال (اگر نیست)
    local_bin = "/root/AlamorTunnel/bin/hysteria"
    if not os.path.exists(local_bin):
        os.system(f"mkdir -p /root/AlamorTunnel/bin")
        os.system(f"curl -L -o {local_bin} https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64")
        os.system(f"chmod +x {local_bin}")

    # 2. تولید کانفیگ کلاینت
    # نکته: برای Port Hopping آدرس سرور را به صورت بازه پورت می‌دهیم
    hopping_addr = f"{server_ip}:{HOP_RANGE}"
    
    # دانلود سرتیفیکیت از سرور خارج برای پین کردن (امنیت بالا)
    # (در نسخه ساده از insecure: true استفاده می‌کنیم)

    client_conf = {
        "server": hopping_addr, # استفاده از بازه پورت برای هاپینگ
        "auth": config['password'],
        "tls": {
            "sni": "www.bing.com", # باید با Masquerade سرور یکی باشد
            "insecure": True       # چون Self-signed است
        },
        "transport": {
            "type": "udp",
            "udp": {
                "hopInterval": "30s" # تغییر پورت هر ۳۰ ثانیه
            }
        },
        "bandwidth": {
            "up": config.get('up_mbps', '100 mbps'),
            "down": config.get('down_mbps', '100 mbps')
        },
        # ساکس و HTTP برای اتصال پنل یا کاربر
        "socks5": {
            "listen": "127.0.0.1:1080"
        },
        "http": {
            "listen": "127.0.0.1:8080"
        }
    }
    
    # اگر پورت فورواردینگ خواسته شده (برای تانل کردن پورت‌های خاص)
    if 'ports' in config and config['ports']:
        # پورت فورواردینگ TCP
        tcp_fw = []
        udp_fw = []
        for p in config['ports']:
            tcp_fw.append({
                "listen": f"0.0.0.0:{p}",
                "remote": f"127.0.0.1:{p}" # فرض بر این است که مقصد روی خود سرور خارج است
            })
            udp_fw.append({
                "listen": f"0.0.0.0:{p}",
                "remote": f"127.0.0.1:{p}",
                "timeout": "60s"
            })
        client_conf['tcpForwarding'] = tcp_fw
        client_conf['udpForwarding'] = udp_fw

    # ذخیره کانفیگ
    with open(CLIENT_CONFIG_PATH, 'w') as f:
        yaml.dump(client_conf, f)

    # 3. ساخت سرویس کلاینت
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

    # 4. استارت
    os.system("systemctl daemon-reload && systemctl enable hysteria-client && systemctl restart hysteria-client")
    
    return True