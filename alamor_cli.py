#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import socket
import requests
from colorama import init, Fore, Style, Back
from tqdm import tqdm

# Initialize Colorama
init(autoreset=True)

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel"
GITHUB_REPO = "https://github.com/Alamor/AlamorTunnel"  # لینک پیش‌فرض (قابل تغییر)
TELEGRAM_CHANNEL = "https://t.me/Alamor_Network"
VERSION = "v3.5.0"

class AlamorCLI:
    def __init__(self):
        self.banner_color = Fore.CYAN + Style.BRIGHT
        self.text_color = Fore.WHITE
        self.option_color = Fore.YELLOW
        self.accent_color = Fore.MAGENTA
        self.success = Fore.GREEN + " [✓] "
        self.error = Fore.RED + " [✖] "
        self.info = Fore.BLUE + " [i] "
        self.warning = Fore.YELLOW + " [!] "
        
        self.public_ip = self.get_public_ip()
        self.domain = self.get_configured_domain()

    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')

    def get_public_ip(self):
        try:
            return subprocess.check_output("curl -s --max-time 2 ifconfig.me", shell=True).decode().strip()
        except:
            return "127.0.0.1"

    def get_configured_domain(self):
        # بررسی فایل‌های Nginx برای پیدا کردن دامنه فعال
        try:
            sites = os.listdir("/etc/nginx/sites-enabled/")
            for site in sites:
                if site != "default":
                    return site # معمولا اسم فایل کانفیگ همان دامنه است
        except:
            pass
        return None

    def draw_header(self):
        self.clear_screen()
        # Cyberpunk Style Header
        print(f"{self.banner_color}╔══════════════════════════════════════════════════════════════╗")
        print(f"║ {Fore.MAGENTA}  _   _   _   _   _   _   _   _   _   _   _   _   _   _   _  {self.banner_color}║")
        print(f"║ {Fore.MAGENTA} / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ {self.banner_color}║")
        print(f"║ {Fore.MAGENTA}( A | L | A | M | O | R |   | T | U | N | N | E | L |   | + ){self.banner_color}║")
        print(f"║ {Fore.MAGENTA} \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ {self.banner_color}║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        # Server Info Section
        print(f"║ {Fore.WHITE}SERVER IP : {Fore.GREEN}{self.public_ip:<41} {self.banner_color}║")
        
        # Panel Address Logic
        if self.domain:
            url = f"https://{self.domain}"
            ssl_status = f"{Fore.GREEN}ACTIVE (SSL)"
        else:
            url = f"http://{self.public_ip}:5050"
            ssl_status = f"{Fore.RED}NO SSL"
            
        print(f"║ {Fore.WHITE}PANEL URL : {Fore.CYAN}{url:<41} {self.banner_color}║")
        print(f"║ {Fore.WHITE}SSL STATUS: {ssl_status:<50} {self.banner_color}║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║ {Fore.WHITE}GITHUB    : {Fore.BLUE}{'github.com/Alamor':<41} {self.banner_color}║")
        print(f"║ {Fore.WHITE}TELEGRAM  : {Fore.BLUE}{'t.me/Alamor_Network':<41} {self.banner_color}║")
        print(f"║ {Fore.WHITE}VERSION   : {Fore.YELLOW}{VERSION:<41} {self.banner_color}║")
        print(f"╚══════════════════════════════════════════════════════════════╝")
        print("")

    def loading_animation(self, desc="Processing"):
        for _ in tqdm(range(100), desc=desc, bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.CYAN, Fore.RESET), leave=False):
            time.sleep(0.01)

    def update_panel(self):
        print(f"\n{self.info}Checking for updates from GitHub...")
        
        # بررسی اینکه آیا پوشه گیت است یا خیر
        if not os.path.exists(f"{INSTALL_DIR}/.git"):
            print(f"{self.warning}Directory is not a Git repository.")
            print(f"{self.info}Initializing Git and pulling latest version...")
            os.system(f"cd {INSTALL_DIR} && git init && git remote add origin {GITHUB_REPO} 2>/dev/null")
            os.system(f"cd {INSTALL_DIR} && git fetch --all && git reset --hard origin/main")
        else:
             os.system(f"cd {INSTALL_DIR} && git pull")
        
        self.loading_animation("Updating Files")
        print(f"\n{self.success}Update finished!")
        
        # پرسش برای ریستارت
        choice = input(f"{self.option_color}Restart panel to apply changes? (y/n): {Fore.RESET}")
        if choice.lower() == 'y':
            self.restart_panel()
        else:
            input("Press Enter to continue...")

    def show_logs(self):
        print(f"\n{self.info}Showing live logs (Press Ctrl+C to exit)...")
        time.sleep(1)
        try:
            os.system("journalctl -u alamor -f -n 50")
        except KeyboardInterrupt:
            pass

    def restart_panel(self):
        self.loading_animation("Restarting Service")
        os.system("systemctl daemon-reload")
        os.system("systemctl restart alamor")
        print(f"\n{self.success}Panel service restarted!")
        time.sleep(1)

    def setup_ssl(self):
        print(f"\n{self.info}Starting Certbot SSL Setup...")
        domain = input(f"{self.option_color}Enter your domain (e.g., panel.example.com): {Fore.RESET}")
        if not domain: return
        
        # 1. Config Nginx
        nginx_conf = f"""
server {{
    listen 80;
    server_name {domain};

    location / {{
        proxy_pass http://127.0.0.1:5050;
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
        
        # 2. Get Cert
        print(f"{self.info}Requesting Certificate from Let's Encrypt...")
        os.system(f"certbot --nginx -d {domain} --non-interactive --agree-tos -m admin@{domain}")
        print(f"\n{self.success}SSL Setup Complete! Access panel at https://{domain}")
        
        # بروزرسانی دامنه در حافظه
        self.domain = domain
        input("Press Enter to continue...")

    def update_cores(self):
        print(f"\n{self.info}Re-downloading Core Binaries...")
        self.loading_animation("Updating Cores")
        os.system("bash /root/AlamorTunnel/install.sh")
        print(f"\n{self.success}Cores updated!")
        time.sleep(1)

    def reset_password(self):
        new_pass = input(f"\n{self.option_color}Enter new admin password: {Fore.RESET}")
        if new_pass:
            cmd = f'python3 -c "from core.database import update_password; update_password(\'{new_pass}\'); print(\'Done\')"'
            os.system(f"cd {INSTALL_DIR} && {cmd}")
            print(f"{self.success}Password updated.")
            time.sleep(1)

    def menu(self):
        while True:
            self.draw_header()
            
            print(f" {self.accent_color}[ MENU OPTIONS ]{Fore.RESET}")
            print(f" {self.text_color}1) {self.option_color}Start/Restart Panel    {Fore.DARK_GREY}(Apply configs)")
            print(f" {self.text_color}2) {self.option_color}View Live Logs         {Fore.DARK_GREY}(Debug issues)")
            print(f" {self.text_color}3) {self.option_color}Setup Domain & SSL     {Fore.DARK_GREY}(Certbot)")
            print(f" {self.text_color}4) {self.option_color}Update Panel (Git)     {Fore.GREEN}(NEW!)")
            print(f" {self.text_color}5) {self.option_color}Re-install Cores       {Fore.DARK_GREY}(Hysteria/Backhaul)")
            print(f" {self.text_color}6) {self.option_color}Reset Admin Password   {Fore.DARK_GREY}(Recovery)")
            print(f" {self.text_color}0) {self.option_color}Exit")
            
            print(f"\n {Fore.DARK_GREY}Type number and press Enter...")
            choice = input(f" {Fore.CYAN}alamor > {Fore.RESET}")

            if choice == '1':
                self.restart_panel()
            elif choice == '2':
                self.show_logs()
            elif choice == '3':
                self.setup_ssl()
            elif choice == '4':
                self.update_panel()
            elif choice == '5':
                self.update_cores()
            elif choice == '6':
                self.reset_password()
            elif choice == '0':
                self.clear_screen()
                sys.exit()

if __name__ == "__main__":
    if os.geteuid() != 0:
        print(Fore.RED + "Please run as root!")
        sys.exit(1)
    
    cli = AlamorCLI()
    cli.menu()