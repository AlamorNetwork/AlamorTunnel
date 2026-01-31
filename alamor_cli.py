# AlamorTunnel/alamor_cli.py
import os
import sys
import subprocess
import time

# --- رنگ‌بندی استاندارد و واضح ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('clear')

def show_banner():
    print(f"{Colors.GREEN}{Colors.BOLD}")
    print(r"""
    _    _                                   
   / \  | | __ _ _ __ ___   ___  _ __      
  / _ \ | |/ _` | '_ ` _ \ / _ \| '__|     
 / ___ \| | (_| | | | | | | (_) | |        
/_/   \_\_|\__,_|_| |_| |_|\___/|_|        
    SERVER MANAGEMENT CLI v2.1 (Stable)
    """)
    print(f"{Colors.ENDC}")

def get_public_ip():
    commands = [
        "curl -s --max-time 3 ifconfig.me",
        "curl -s --max-time 3 api.ipify.org"
    ]
    for cmd in commands:
        try:
            ip = subprocess.check_output(cmd, shell=True).decode().strip()
            if len(ip) < 20: return ip
        except: continue
    return "Unknown IP"

def menu():
    while True:
        clear_screen()
        show_banner()
        print(f" {Colors.CYAN}1.{Colors.ENDC} Reset Admin Password")
        print(f" {Colors.CYAN}2.{Colors.ENDC} Restart Panel Service")
        print(f" {Colors.CYAN}3.{Colors.ENDC} View Logs (Live)")
        print(f" {Colors.CYAN}4.{Colors.ENDC} Update Panel (Git Pull)")
        print(f" {Colors.CYAN}5.{Colors.ENDC} Show Server IP")
        print(f" {Colors.RED}0. Exit{Colors.ENDC}")
        
        choice = input(f"\n {Colors.BOLD}Select option: {Colors.ENDC}")

        if choice == '1':
            try:
                # FIX: Import inside function to avoid circular imports if any
                from core.database import update_password
                new_pass = input(f" {Colors.YELLOW}Enter new admin password: {Colors.ENDC}")
                if new_pass:
                    # FIX: Removed 'admin' argument
                    update_password(new_pass)
                    print(f"\n {Colors.GREEN}[✔] Password updated successfully.{Colors.ENDC}")
                else:
                    print(f"\n {Colors.RED}[!] Password cannot be empty.{Colors.ENDC}")
            except Exception as e:
                print(f"\n {Colors.RED}[X] Error: {e}{Colors.ENDC}")
            input(f"\n Press Enter to continue...")
            
        elif choice == '2':
            print(f"\n {Colors.YELLOW}[*] Restarting alamor.service...{Colors.ENDC}")
            os.system("systemctl restart alamor")
            print(f" {Colors.GREEN}[✔] Service restarted.{Colors.ENDC}")
            time.sleep(1)

        elif choice == '3':
            print(f"\n {Colors.YELLOW}[*] Press Ctrl+C to exit logs...{Colors.ENDC}")
            try:
                os.system("journalctl -u alamor -f -n 50")
            except KeyboardInterrupt:
                pass
            
        elif choice == '4':
            print(f"\n {Colors.YELLOW}[*] Pulling latest changes...{Colors.ENDC}")
            os.system("git reset --hard origin/main")
            if os.system("git pull") == 0:
                print(f"\n {Colors.GREEN}[✔] Updated. Restarting service...{Colors.ENDC}")
                os.system("systemctl restart alamor")
            else:
                print(f"\n {Colors.RED}[!] Update failed.{Colors.ENDC}")
            input("\n Press Enter...")
            
        elif choice == '5':
             print(f"\n {Colors.YELLOW}[*] Fetching IP...{Colors.ENDC}")
             print(f" {Colors.GREEN}Server IP: {get_public_ip()}{Colors.ENDC}")
             input("\n Press Enter...")

        elif choice == '0':
            sys.exit()

if __name__ == "__main__":
    try:
        menu()
    except KeyboardInterrupt:
        sys.exit()