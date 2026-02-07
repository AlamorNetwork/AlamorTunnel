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
VERSION = "v3.8.0"

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
            if self.is_port_open(5050)
            else Fore.RED + "CLOSED"
        )

        panel_url = (
            f"https://{self.domain}"
            if self.domain
            else f"http://{self.public_ip}:5050"
        )

        print(f"{self.banner_color}╔══════════════════════════════════════════════════════════════╗")
        print(f"║  A L A M O R   T U N N E L   +                              ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║ SERVER IP   : {Fore.GREEN}{self.public_ip:<43}{self.banner_color}║")
        print(f"║ PANEL URL   : {Fore.CYAN}{panel_url:<43}{self.banner_color}║")
        print(f"║ SSL STATUS  : {self.ssl_status():<43}{self.banner_color}║")
        print(f"║ SERVICE     : {service_color:<43}{self.banner_color}║")
        print(f"║ PORT 5050   : {port_status:<43}{self.banner_color}║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║ GITHUB      : github.com/Alamor                             ║")
        print(f"║ TELEGRAM    : t.me/Alamor_Network                           ║")
        print(f"║ VERSION     : {VERSION:<45}║")
        print(f"╚══════════════════════════════════════════════════════════════╝\n")

    # ---------- ACTIONS ----------

    def restart_panel(self):
        print(self.info, "Restarting panel...")
        os.system("systemctl daemon-reload")
        os.system("systemctl restart alamor")
        time.sleep(1)

    def show_logs(self):
        os.system("journalctl -u alamor -f -n 50")

    def update_panel(self):
        print(self.info, "Updating from GitHub...")
        os.system(f"cd {INSTALL_DIR} && git pull")

    def setup_ssl(self):
        domain = input("Enter domain: ").strip()
        if not domain:
            return
        os.system(f"certbot --nginx -d {domain}")
        self.domain = domain

    # ---------- MENU ----------

    def menu(self):
        while True:
            self.draw_header()
            print(f"{self.accent_color}[ MENU OPTIONS ]\n")
            print(" 1) Start / Restart Panel")
            print(" 2) View Live Logs")
            print(" 3) Setup Domain & SSL")
            print(" 4) Update Panel (Git)")
            print(" 0) Exit\n")

            choice = input(" alamor > ").strip()

            if choice == "1":
                self.restart_panel()
            elif choice == "2":
                self.show_logs()
            elif choice == "3":
                self.setup_ssl()
            elif choice == "4":
                self.update_panel()
            elif choice == "0":
                sys.exit()

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("Run as root!")
        sys.exit(1)

    cli = AlamorCLI()
    cli.menu()
