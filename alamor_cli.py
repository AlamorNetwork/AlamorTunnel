import sys
import os
import sqlite3
import subprocess
import time
import re

# تلاش برای ایمپورت ماژول‌ها؛ اگر نصب نبودند ارور ندهد
try:
    from core.config_loader import load_config
    from core.database import DB_PATH
except ImportError:
    # مسیر پیش‌فرض برای مواقعی که در پوشه نیستیم
    sys.path.append('/root/AlamorTunnel')
    from core.config_loader import load_config
    from core.database import DB_PATH

# --- COLORS ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('clear')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- IP FUNCTION ---
def get_public_ip():
    """دریافت آی‌پی سرور از چندین منبع مختلف با اعتبارسنجی"""
    providers = [
        "curl -s --max-time 3 https://api.ipify.org",
        "curl -s --max-time 3 https://icanhazip.com",
        "curl -s --max-time 3 http://ifconfig.me/ip",
        "hostname -I | awk '{print $1}'" 
    ]
    
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')

    for cmd in providers:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output):
                return output
        except:
            continue
            
    return "Unknown-IP"

# --- CORE FUNCTIONS ---

def show_info():
    """نمایش اطلاعات حیاتی شامل آدرس مخفی"""
    print(f"{Colors.YELLOW}[*] Fetching Server Data...{Colors.RESET}")
    ip = get_public_ip()
        
    config = load_config()
    secret_path = config.get('panel_path', '')
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username='admin'")
        user = c.fetchone()
        conn.close()
        username = user['username']
        password = user['password']
    except:
        username = "admin"
        password = "Unknown (DB Error)"

    clear_screen()
    print(f"\n{Colors.CYAN}=== ALAMOR PANEL STATUS ==={Colors.RESET}")
    print(f"{Colors.YELLOW}[+] Server IP:{Colors.RESET}   {ip}")
    print(f"{Colors.YELLOW}[+] Admin User:{Colors.RESET}  {username}")
    print(f"{Colors.YELLOW}[+] Admin Pass:{Colors.RESET}  {password}")
    
    print(f"\n{Colors.GREEN}[+] LOGIN URLs:{Colors.RESET}")
    if secret_path:
        print(f"  ➜ {Colors.BOLD}Secure (SSL):{Colors.RESET}  https://{ip}/{secret_path}/dashboard")
        if ip != "Unknown-IP":
             print(f"  ➜ {Colors.BOLD}Local (HTTP):{Colors.RESET}  http://{ip}:5050/{secret_path}/dashboard")
    else:
        print(f"  ➜ {Colors.BOLD}Standard:{Colors.RESET}      http://{ip}:5050/")
    
    print(f"\n{Colors.CYAN}==========================={Colors.RESET}")

def manage_firewall(action, port, proto='tcp'):
    if action not in ['allow', 'deny']:
        print(f"{Colors.RED}[!] Invalid action. Use 'allow' or 'deny'.{Colors.RESET}")
        return

    print(f"{Colors.YELLOW}[*] {action.capitalize()}ing port {port}/{proto}...{Colors.RESET}")
    os.system(f"ufw {action} {port}/{proto}")
    os.system("ufw reload")
    print(f"{Colors.GREEN}[✔] Firewall updated successfully.{Colors.RESET}")

def reset_password():
    conn = get_db_connection()
    conn.execute("UPDATE users SET password='admin' WHERE username='admin'")
    conn.commit()
    conn.close()
    print(f"\n{Colors.GREEN}[✔] Password reset to: admin{Colors.RESET}")

def update_panel():
    """آپدیت پنل از گیت‌هاب"""
    print(f"\n{Colors.YELLOW}[*] Pulling latest changes from Git...{Colors.RESET}")
    # ریست کردن تغییرات لوکال برای جلوگیری از تداخل
    os.system("git fetch --all")
    os.system("git reset --hard origin/main")
    
    if os.system("git pull") == 0:
        print(f"\n{Colors.GREEN}[✔] Source code updated.{Colors.RESET}")
        print(f"{Colors.YELLOW}[*] Restarting alamor service...{Colors.RESET}")
        os.system("systemctl restart alamor")
        print(f"{Colors.GREEN}[✔] Service restarted successfully.{Colors.RESET}")
    else:
        print(f"\n{Colors.RED}[!] Update failed. Check internet connection.{Colors.RESET}")

def interactive_menu():
    while True:
        clear_screen()
        print(f"{Colors.GREEN}{Colors.BOLD}")
        print(r"""
    _    _                                   
   / \  | | __ _ _ __ ___   ___  _ __      
  / _ \ | |/ _` | '_ ` _ \ / _ \| '__|     
 / ___ \| | (_| | | | | | | (_) | |        
/_/   \_\_|\__,_|_| |_| |_|\___/|_|        
    """)
        print(f"{Colors.CYAN}   ADMIN CLI DASHBOARD{Colors.RESET}")
        print(f"{Colors.GREEN}============================{Colors.RESET}")
        print(f" {Colors.CYAN}1.{Colors.RESET} Show Panel Info & URLs")
        print(f" {Colors.CYAN}2.{Colors.RESET} Reset Admin Password")
        print(f" {Colors.CYAN}3.{Colors.RESET} Restart Panel Service")
        print(f" {Colors.CYAN}4.{Colors.RESET} Manage Firewall (Open Port)")
        print(f" {Colors.CYAN}5.{Colors.RESET} Update Panel (Git Pull)")
        print(f" {Colors.CYAN}6.{Colors.RESET} Live Logs")
        print(f" {Colors.RED}0. Exit{Colors.RESET}")
        
        choice = input(f"\n {Colors.BOLD}Select > {Colors.RESET}")

        if choice == '1':
            show_info()
            input("\nPress Enter...")
        elif choice == '2':
            reset_password()
            input("\nPress Enter...")
        elif choice == '3':
            os.system("systemctl restart alamor")
            print(f"{Colors.GREEN}[✔] Service Restarted.{Colors.RESET}")
            time.sleep(1)
        elif choice == '4':
            p = input("Enter Port: ")
            manage_firewall('allow', p)
            input("\nPress Enter...")
        elif choice == '5':
            update_panel()
            input("\nPress Enter...")
        elif choice == '6':
            try:
                os.system("journalctl -u alamor -f -n 50")
            except: pass
        elif choice == '0':
            sys.exit()

# --- MAIN ENTRY POINT ---
if __name__ == '__main__':
    # اگر آرگومان داشت (مثلاً: alamor info)
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'info':
            show_info()
        elif cmd == 'reset_pass':
            reset_password()
        elif cmd == 'update':
            update_panel()
        elif cmd == 'firewall':
            # usage: alamor firewall allow 443 tcp
            if len(sys.argv) >= 4:
                manage_firewall(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv)>4 else 'tcp')
            else:
                print("Usage: alamor firewall <allow/deny> <port> [protocol]")
        else:
            print(f"Unknown command: {cmd}")
    else:
        # اگر بدون آرگومان بود، منو را باز کن
        interactive_menu()