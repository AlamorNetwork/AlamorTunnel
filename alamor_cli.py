import sys
import os
import sqlite3
import subprocess
import time
import re

# تلاش برای ایمپورت ماژول‌ها
try:
    from core.config_loader import load_config
    from core.database import DB_PATH
except ImportError:
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
            if ip_pattern.match(output): return output
        except: continue
    return "Unknown-IP"

# --- CORE FUNCTIONS ---
def show_info():
    print(f"{Colors.YELLOW}[*] Fetching Server Data...{Colors.RESET}")
    ip = get_public_ip()
        
    config = load_config()
    secret_path = config.get('panel_path', '')
    panel_domain = config.get('panel_domain', '') # خواندن دامنه از کانفیگ
    
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
    if panel_domain:
        print(f"{Colors.YELLOW}[+] Domain:{Colors.RESET}      {panel_domain}")
        
    print(f"{Colors.YELLOW}[+] Admin User:{Colors.RESET}  {username}")
    print(f"{Colors.YELLOW}[+] Admin Pass:{Colors.RESET}  {password}")
    
    print(f"\n{Colors.GREEN}[+] LOGIN URLs:{Colors.RESET}")
    if secret_path:
        # اگر دامنه داریم، از دامنه استفاده کن، وگرنه IP
        secure_host = panel_domain if panel_domain else ip
        
        print(f"  ➜ {Colors.BOLD}Secure (SSL):{Colors.RESET}  https://{secure_host}/{secret_path}/dashboard")
        
        if ip != "Unknown-IP":
             print(f"  ➜ {Colors.BOLD}Local (HTTP):{Colors.RESET}  http://{ip}:5050/{secret_path}/dashboard")
    else:
        print(f"  ➜ {Colors.BOLD}Standard:{Colors.RESET}      http://{ip}:5050/")
    
    print(f"\n{Colors.CYAN}==========================={Colors.RESET}")

def manage_firewall(action, port, proto='tcp'):
    if action not in ['allow', 'deny']:
        print(f"{Colors.RED}[!] Invalid action.{Colors.RESET}")
        return
    print(f"{Colors.YELLOW}[*] {action.capitalize()}ing port {port}/{proto}...{Colors.RESET}")
    os.system(f"ufw {action} {port}/{proto}")
    os.system("ufw reload")
    print(f"{Colors.GREEN}[✔] Done.{Colors.RESET}")

def reset_password():
    conn = get_db_connection()
    conn.execute("UPDATE users SET password='admin' WHERE username='admin'")
    conn.commit()
    conn.close()
    print(f"\n{Colors.GREEN}[✔] Password reset to: admin{Colors.RESET}")

def update_panel():
    print(f"\n{Colors.YELLOW}[*] Updating...{Colors.RESET}")
    os.system("git fetch --all && git reset --hard origin/main")
    if os.system("git pull") == 0:
        print(f"{Colors.GREEN}[✔] Updated. Restarting...{Colors.RESET}")
        os.system("systemctl restart alamor")
    else:
        print(f"{Colors.RED}[!] Update failed.{Colors.RESET}")

def interactive_menu():
    while True:
        clear_screen()
        print(f"{Colors.GREEN}{Colors.BOLD}ALAMOR CLI v2.2{Colors.RESET}")
        print(f"1. Show Info & URLs")
        print(f"2. Reset Admin Password")
        print(f"3. Restart Service")
        print(f"4. Manage Firewall")
        print(f"5. Update Panel")
        print(f"6. Live Logs")
        print(f"0. Exit")
        choice = input(f"\n{Colors.BOLD}Select > {Colors.RESET}")
        if choice == '1': show_info(); input("\nPress Enter...")
        elif choice == '2': reset_password(); input("\nPress Enter...")
        elif choice == '3': os.system("systemctl restart alamor"); time.sleep(1)
        elif choice == '4': manage_firewall('allow', input("Port: ")); input("\nEnter...")
        elif choice == '5': update_panel(); input("\nEnter...")
        elif choice == '6': os.system("journalctl -u alamor -f -n 50")
        elif choice == '0': sys.exit()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'info': show_info()
        elif cmd == 'reset_pass': reset_password()
        elif cmd == 'update': update_panel()
        elif cmd == 'firewall': 
            if len(sys.argv) >= 4: manage_firewall(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv)>4 else 'tcp')
        else: interactive_menu()
    else: interactive_menu()