#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import re
import socket
from colorama import init, Fore, Style

init(autoreset=True)

INSTALL_DIR = "/root/AlamorTunnel"
GITHUB_REPO = "https://github.com/Alamor/AlamorTunnel.git"
TELEGRAM_CHANNEL = "https://t.me/Alamor_Network"
VERSION = "v3.9.0"

class AlamorCLI:
    def __init__(self):
        self.banner_color = Fore.CYAN + Style.BRIGHT
        self.text_color = Fore.WHITE
        self.option_color = Fore.YELLOW
        self.accent_color = Fore.MAGENTA
        self.desc_color = Fore.RESET

        self.success = Fore.GREEN + "[OK]"
        self.error = Fore.RED + "[ERR]"
        self.info = Fore.BLUE + "[INFO]"

        self.public_ip = self.get_server_ip()
        self.domain = self.get_configured_domain()
        self.port = self.get_current_port()

    # ---------- SYSTEM INFO ----------

    def get_server_ip(self):
        try:
            out = subprocess.check_output("hostname -I", shell=True).decode().strip()
            if out:
                return out.split()[0]
        except:
            pass
        try:
            out = subprocess.check_output("ifconfig", shell=True).decode()
            ips = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', out)
            for ip in ips:
                if not ip.startswith("127."):
                    return ip
        except:
            pass
        return "127.0.0.1"

    def get_configured_domain(self):
        try:
            path = "/etc/nginx/sites-enabled/"
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f != "default":
                        return f
        except:
            pass
        return None
    
    def get_current_port(self):
        # تلاش برای خواندن پورت از فایل app.py
        try:
            with open(f"{INSTALL_DIR}/app.py", "r") as f:
                content = f.read()
                match = re.search(r"port\s*=\s*(\d+)", content)
                if match:
                    return int(match.group(1))
        except:
            pass
        return 5050 # پیش‌فرض

    def is_port_open(self, port):
        try:
            s = socket.socket()
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except:
            return False

    def service_status(self):
        try:
            out = subprocess.check_output(
                "systemctl is-active alamor", shell=True
            ).decode().strip()
            return out
        except:
            return "not-installed"

    def ssl_status(self):
        if not self.domain:
            return Fore.RED + "NO SSL"
        cert = f"/etc/letsencrypt/live/{self.domain}/fullchain.pem"
        if os.path.exists(cert):
            return Fore.GREEN + "ACTIVE (SSL)"
        return Fore.YELLOW + "NGINX ONLY (NO SSL)"

    # ---------- UI ----------

    def clear(self):
        os.system("clear" if os.name == "posix" else "cls")

    def draw_header(self):
        self.clear()

        service = self.service_status()
        service_color = {
            "active": Fore.GREEN + "ACTIVE",
            "inactive": Fore.RED + "STOPPED",
            "failed": Fore.RED + "FAILED",
            "not-installed": Fore.YELLOW + "NOT INSTALLED"
        }.get(service, Fore.YELLOW + service.upper())

        port_status = (
            Fore.GREEN + "OPEN"
            if self.is_port_open(self.port)
            else Fore.RED + "CLOSED"
        )

        panel_url = (
            f"https://{self.domain}"
            if self.domain
            else f"http://{self.public_ip}:{self.port}"
        )

        print(f"{self.banner_color}╔══════════════════════════════════════════════════════════════╗")
        print(f"║  A L A M O R   T U N N E L   +                              ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║ SERVER IP   : {Fore.GREEN}{self.public_ip:<43}{self.banner_color}║")
        print(f"║ PANEL URL   : {Fore.CYAN}{panel_url:<43}{self.banner_color}║")
        print(f"║ SSL STATUS  : {self.ssl_status():<43}{self.banner_color}║")
        print(f"║ SERVICE     : {service_color:<43}{self.banner_color}║")
        print(f"║ PORT {self.port:<4}   : {port_status:<43}{self.banner_color}║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║ GITHUB      : github.com/Alamor                              ║")
        print(f"║ TELEGRAM    : t.me/Alamor_Network                            ║")
        print(f"║ VERSION     : {VERSION:<45}║")
        print(f"╚══════════════════════════════════════════════════════════════╝\n")

    # ---------- ACTIONS ----------

    def restart_panel(self):
        print(f"\n{self.info} Restarting panel...")
        os.system("systemctl daemon-reload")
        os.system("systemctl restart alamor")
        time.sleep(1)

    def show_logs(self):
        os.system("journalctl -u alamor -f -n 50")

    def update_panel(self):
        print(f"\n{self.info} Updating from GitHub...")
        os.system(f"cd {INSTALL_DIR} && git pull")
        self.restart_panel()

    def setup_ssl(self):
        print(f"\n{self.info} Setup SSL...")
        domain = input(f"{self.option_color} Enter domain: {Fore.RESET}").strip()
        if not domain:
            return
        
        # 1. Update Nginx Config
        nginx_conf = f"""
server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass http://127.0.0.1:{self.port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
"""
        with open(f"/etc/nginx/sites-available/{domain}", "w") as f:
            f.write(nginx_conf)
        
        os.system(f"ln -sf /etc/nginx/sites-available/{domain} /etc/nginx/sites-enabled/")
        os.system("systemctl restart nginx")

        # 2. Certbot
        os.system(f"certbot --nginx -d {domain} --non-interactive --agree-tos -m admin@{domain}")
        self.domain = domain

    def change_credentials(self):
        print(f"\n{self.info} Change Admin Credentials")
        new_user = input(f"{self.option_color} New Username: {Fore.RESET}").strip()
        new_pass = input(f"{self.option_color} New Password: {Fore.RESET}").strip()
        
        if not new_user or not new_pass:
            print(f"{self.error} Username/Password cannot be empty.")
            time.sleep(1)
            return

        # اجرای دستور پایتون برای آپدیت دیتابیس
        cmd = f"""cd {INSTALL_DIR} && python3 -c "import sqlite3; conn = sqlite3.connect('database.db'); c = conn.cursor(); c.execute(\\\"UPDATE users SET username='{new_user}', password='{new_pass}'\\\"); conn.commit(); print('Credentials Updated!')" """
        os.system(cmd)
        print(f"{self.success} Login details changed successfully.")
        time.sleep(1)

    def change_port(self):
        print(f"\n{self.info} Change Panel Port")
        print(f"{self.option_color} Current Port: {self.port}")
        new_port = input(f"{self.option_color} Enter new port (default 5050): {Fore.RESET}").strip()
        
        if not new_port.isdigit():
            print(f"{self.error} Invalid port.")
            return
        
        # 1. Update app.py
        app_path = f"{INSTALL_DIR}/app.py"
        os.system(f"sed -i 's/port=[0-9]*/port={new_port}/g' {app_path}")
        
        # 2. Update Nginx if exists
        if self.domain:
            nginx_conf = f"/etc/nginx/sites-enabled/{self.domain}"
            if os.path.exists(nginx_conf):
                os.system(f"sed -i 's/127.0.0.1:[0-9]*/127.0.0.1:{new_port}/g' {nginx_conf}")
                os.system("systemctl restart nginx")
        
        self.port = int(new_port)
        print(f"{self.success} Port changed to {new_port}.")
        self.restart_panel()

    # ---------- MENU ----------

    def menu(self):
        while True:
            self.draw_header()
            print(f"{self.accent_color}[ MENU OPTIONS ]\n")
            print(f" 1) Start / Restart Panel")
            print(f" 2) View Live Logs")
            print(f" 3) Setup Domain & SSL")
            print(f" 4) Update Panel (Git)")
            print(f" 5) Change User/Pass  {Fore.GREEN}(NEW!)")
            print(f" 6) Change Panel Port {Fore.GREEN}(NEW!)")
            print(f" 0) Exit\n")

            choice = input(" alamor > ").strip()

            if choice == "1":
                self.restart_panel()
            elif choice == "2":
                self.show_logs()
            elif choice == "3":
                self.setup_ssl()
            elif choice == "4":
                self.update_panel()
            elif choice == "5":
                self.change_credentials()
            elif choice == "6":
                self.change_port()
            elif choice == "0":
                sys.exit()

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run as root!")
        sys.exit(1)

    cli = AlamorCLI()
    cli.menu()