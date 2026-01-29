import os
import sys
import subprocess
import time

# کلاس رنگ‌ها (کامل شده)
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'   # اضافه شد
    GREEN = '\033[92m'
    YELLOW = '\033[93m' # اضافه شد (باگ قبلی اینجا بود)
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('clear')

def show_banner():
    print(f"{Colors.GREEN}")
    print(r"""
    _    _                                   
   / \  | | __ _ _ __ ___   ___  _ __      
  / _ \ | |/ _` | '_ ` _ \ / _ \| '__|     
 / ___ \| | (_| | | | | | | (_) | |        
/_/   \_\_|\__,_|_| |_| |_|\___/|_|        
    SERVER MANAGEMENT CLI v1.1
    """)
    print(f"{Colors.ENDC}")

def get_public_ip():
    """تلاش برای گرفتن آی‌پی از چند منبع مختلف"""
    commands = [
        "curl -s https://api.ipify.org",
        "curl -s ifconfig.me",
        "curl -s icanhazip.com"
    ]
    for cmd in commands:
        try:
            ip = subprocess.check_output(cmd, shell=True, timeout=5).decode().strip()
            if ip and len(ip) < 20: # بررسی اینکه خروجی واقعا آی‌پی باشد
                return ip
        except:
            continue
    return "Unknown (Check Network)"

def menu():
    while True:
        clear_screen()
        show_banner()
        print(f"{Colors.CYAN}1.{Colors.ENDC} Reset Admin Password")
        print(f"{Colors.CYAN}2.{Colors.ENDC} Restart Panel Service")
        print(f"{Colors.CYAN}3.{Colors.ENDC} View Logs (Live)")
        print(f"{Colors.CYAN}4.{Colors.ENDC} Update Panel (Git Pull)")
        print(f"{Colors.CYAN}5.{Colors.ENDC} Show Server IP")
        print(f"{Colors.FAIL}0.{Colors.ENDC} Exit")
        
        choice = input(f"\n{Colors.BOLD}Select option: {Colors.ENDC}")

        if choice == '1':
            from core.database import update_password
            new_pass = input("Enter new admin password: ")
            if new_pass:
                update_password('admin', new_pass)
                print(f"{Colors.GREEN}[+] Password updated successfully.{Colors.ENDC}")
            input("Press Enter...")
            
        elif choice == '2':
            os.system("systemctl restart alamor")
            print(f"{Colors.GREEN}[+] Service restarted.{Colors.ENDC}")
            input("Press Enter...")

        elif choice == '3':
            print(f"{Colors.YELLOW}Press Ctrl+C to exit logs...{Colors.ENDC}")
            try:
                os.system("journalctl -u alamor -f")
            except KeyboardInterrupt:
                pass
            
        elif choice == '4':
            print(f"{Colors.YELLOW}[*] Pulling latest changes from GitHub...{Colors.ENDC}")
            # استفاده از git reset برای جلوگیری از کانفلیکت فایل‌های لوکال
            os.system("git reset --hard origin/main")
            result = os.system("git pull")
            
            if result == 0:
                print(f"{Colors.GREEN}[+] Update finished. Restarting service...{Colors.ENDC}")
                os.system("systemctl restart alamor")
            else:
                print(f"{Colors.FAIL}[!] Update failed. Check internet connection.{Colors.ENDC}")
            input("Press Enter...")
            
        elif choice == '5':
             print(f"{Colors.YELLOW}[*] Fetching IP...{Colors.ENDC}")
             ip = get_public_ip()
             print(f"\n{Colors.GREEN}Server IP: {ip}{Colors.ENDC}\n")
             input("Press Enter...")

        elif choice == '0':
            sys.exit()

if __name__ == "__main__":
    menu()