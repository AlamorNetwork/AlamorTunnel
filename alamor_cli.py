import os
import sys
import subprocess
from core.database import update_password

# رنگ‌ها برای ترمینال
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
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
    SERVER MANAGEMENT CLI v1.0
    """)
    print(f"{Colors.ENDC}")

def menu():
    while True:
        clear_screen()
        show_banner()
        print(f"{Colors.BLUE}1.{Colors.ENDC} Reset Admin Password")
        print(f"{Colors.BLUE}2.{Colors.ENDC} Restart Panel Service")
        print(f"{Colors.BLUE}3.{Colors.ENDC} View Logs (Live)")
        print(f"{Colors.BLUE}4.{Colors.ENDC} Update Panel (Git Pull)")
        print(f"{Colors.BLUE}5.{Colors.ENDC} Show Server IP")
        print(f"{Colors.BLUE}0.{Colors.ENDC} Exit")
        
        choice = input(f"\n{Colors.BOLD}Select option: {Colors.ENDC}")

        if choice == '1':
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
            print(f"{Colors.WARNING}Press Ctrl+C to exit logs...{Colors.ENDC}")
            try:
                os.system("journalctl -u alamor -f")
            except KeyboardInterrupt:
                pass
            
        elif choice == '4':
            print(f"{Colors.YELLOW}[*] Pulling latest changes...{Colors.ENDC}")
            os.system("git pull")
            print(f"{Colors.GREEN}[+] Update finished. Restarting service...{Colors.ENDC}")
            os.system("systemctl restart alamor")
            input("Press Enter...")
            
        elif choice == '5':
             os.system("curl -s ifconfig.me")
             print("")
             input("Press Enter...")

        elif choice == '0':
            sys.exit()

if __name__ == "__main__":
    menu()