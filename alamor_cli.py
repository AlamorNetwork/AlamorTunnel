#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import requests
from colorama import init, Fore, Style

# Initialize Colorama
init(autoreset=True)

# --- CONFIGURATION ---
INSTALL_DIR = "/root/AlamorTunnel"
GITHUB_REPO = "https://github.com/Alamor/AlamorTunnel.git"
TELEGRAM_CHANNEL = "https://t.me/Alamor_Network"
VERSION = "v3.6.0"

class AlamorCLI:
    def __init__(self):
        self.banner_color = Fore.CYAN + Style.BRIGHT
        self.text_color = Fore.WHITE
        self.option_color = Fore.YELLOW
        self.accent_color = Fore.MAGENTA
        self.dim_color = Fore.LIGHTBLACK_EX 
        
        self.success = Fore.GREEN + " [✓] "
        self.error = Fore.RED + " [✖] "
        self.info = Fore.BLUE + " [i] "
        self.warning = Fore.YELLOW + " [!] "
        
        self.domain = self.get_configured_domain()
        self.public_ip = self.get_server_ip()

    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')

    def get_server_ip(self):
        """دریافت IP سرور مستقیماً از دستورات سیستم عامل"""
        try:
            # روش ۱: استفاده از hostname -I (معمولاً اولین IP پابلیک است)
            ip = subprocess.check_output(['hostname', '-I']).decode().strip().split()[0]
            if ip: return ip
        except:
            pass
            
        try:
            # روش ۲: استفاده از ip route get 1 (مسیر پیش‌فرض اینترنت)
            # این دستور IPای که به اینترنت وصل است را برمی‌گرداند
            output = subprocess.check_output("ip route get 1 | awk '{print $7}'", shell=True).decode().strip()
            if output: return output
        except:
            pass

        return "127.0.0.1"

    def get_configured_domain(self):
        try:
            if os.path.exists("/etc/nginx/sites-enabled/"):
                sites = os.listdir("/etc/nginx/sites-enabled/")
                for site in sites:
                    if site != "default":
                        return site
        except:
            pass
        return None

    def draw_header(self):
        self.clear_screen()
        print(f"{self.banner_color}╔══════════════════════════════════════════════════════════════╗")
        print(f"║ {Fore.MAGENTA}  _   _   _   _   _   _   _   _   _   _   _   _   _   _   _  {self.banner_color}║")
        print(f"║ {Fore.MAGENTA} / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ {self.banner_color}║")
        print(f"║ {Fore.MAGENTA}( A | L | A | M | O | R |   | T | U | N | N | E | L |   | + ){self.banner_color}║")
        print(f"║ {Fore.MAGENTA} \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ {self.banner_color}║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        print(f"║ {Fore.WHITE}SERVER IP : {Fore.GREEN}{self.public_ip:<41} {self.banner_color}║")
        
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
        chars = "/-\|"
        for i in range(20):
            time.sleep(0.05)
            sys.stdout.write(f"\r{self.info}{desc} {chars[i % 4]}")
            sys.stdout.flush()
        print()

    def update_panel(self):
        print(f"\n{self.info}Checking for updates...")
        if not os.path.exists(f"{INSTALL_DIR}/.git"):
            os.system(f"cd {INSTALL_DIR} && git init && git remote add origin {GITHUB_REPO} 2>/dev/null")
            os.system(f"cd {INSTALL_DIR} && git fetch --all && git reset --hard origin/main")
        else:
             os.system(f"cd {INSTALL_DIR} && git pull")
        
        print(f"\n{self.success}Update finished!")
        try:
            choice = input(f"{self.option_color}Restart panel to apply changes? (y/n): {Fore.RESET}")
            if choice.lower() == 'y':
                self.restart_panel()
        except KeyboardInterrupt:
            pass

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
        try:
            domain = input(f"{self.option_color}Enter your domain (e.g., panel.example.com): {Fore.RESET}")
        except KeyboardInterrupt:
            return

        if not domain: return
        
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
        
        print(f"{self.info}Requesting Certificate...")
        os.system(f"certbot --nginx -d {domain} --non-interactive --agree-tos -m admin@{domain}")
        print(f"\n{self.success}SSL Setup Complete! Access panel at https://{domain}")
        
        self.domain = domain
        input("Press Enter to continue...")

    def update_cores(self):
        print(f"\n{self.info}Re-downloading Core Binaries...")
        self.loading_animation("Updating Cores")
        os.system("bash /root/AlamorTunnel/install.sh")
        print(f"\n{self.success}Cores updated!")
        time.sleep(1)

    def reset_password(self):
        try:
            new_pass = input(f"\n{self.option_color}Enter new admin password: {Fore.RESET}")
            if new_pass:
                cmd = f'python3 -c "from core.database import update_password; update_password(\'{new_pass}\'); print(\'Done\')"'
                os.system(f"cd {INSTALL_DIR} && {cmd}")
                print(f"{self.success}Password updated.")
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    def menu(self):
        while True:
            self.draw_header()
            
            print(f" {self.accent_color}[ MENU OPTIONS ]{Fore.RESET}")
            print(f" {self.text_color}1) {self.option_color}Start/Restart Panel    {self.dim_color}(Apply configs)")
            print(f" {self.text_color}2) {self.option_color}View Live Logs         {self.dim_color}(Debug issues)")
            print(f" {self.text_color}3) {self.option_color}Setup Domain & SSL     {self.dim_color}(Certbot)")
            print(f" {self.text_color}4) {self.option_color}Update Panel (Git)     {Fore.GREEN}(NEW!)")
            print(f" {self.text_color}5) {self.option_color}Re-install Cores       {self.dim_color}(Hysteria/Backhaul)")
            print(f" {self.text_color}6) {self.option_color}Reset Admin Password   {self.dim_color}(Recovery)")
            print(f" {self.text_color}0) {self.option_color}Exit")
            
            print(f"\n {self.dim_color}Type number and press Enter...")
            try:
                choice = input(f" {Fore.CYAN}alamor > {Fore.RESET}")
            except KeyboardInterrupt:
                print("\nGoodbye!")
                sys.exit()

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
    
    # نصب خودکار پکیج‌های ضروری اگر نبودند
    try:
        import requests
        from colorama import init
    except ImportError:
        print("Installing required libraries...")
        os.system("pip3 install requests colorama tqdm --break-system-packages")
        os.execv(sys.executable, ['python3'] + sys.argv)

    cli = AlamorCLI()
    cli.menu()