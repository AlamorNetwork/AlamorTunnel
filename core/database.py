import sqlite3
import random
import string
import json
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "alamor.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY, ip TEXT UNIQUE, port INTEGER DEFAULT 22, username TEXT DEFAULT 'root', status TEXT DEFAULT 'disconnected')''')
    
    # جدول جدید تانل‌ها با تمام جزئیات کانفیگ
    c.execute('''CREATE TABLE IF NOT EXISTS tunnels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        transport TEXT,
        tunnel_port INTEGER,
        token TEXT,
        config_json TEXT,  -- ذخیره تمام تنظیمات پیشرفته بصورت JSON
        status TEXT DEFAULT 'active'
    )''')
    
    conn.commit()
    conn.close()

# ... (بقیه توابع قبلی مثل create_initial_user, verify_user ثابت می‌مانند) ...

def create_initial_user():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        chars = string.ascii_letters + string.digits
        raw_pass = ''.join(random.choice(chars) for i in range(12))
        hashed_pass = generate_password_hash(raw_pass)
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', hashed_pass))
        conn.commit()
        print(f"\n[+] Admin Created. Password: {raw_pass}\n")
    conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user and check_password_hash(user[0], password):
        return True
    return False

def update_password(username, new_password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    hashed_pass = generate_password_hash(new_password)
    c.execute("UPDATE users SET password=? WHERE username=?", (hashed_pass, username))
    conn.commit()
    conn.close()

def add_or_update_server(ip, port, username, status="connected"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""INSERT INTO servers (ip, port, username, status) VALUES (?, ?, ?, ?) 
                 ON CONFLICT(ip) DO UPDATE SET status=excluded.status, port=excluded.port""", (ip, port, username, status))
    conn.commit()
    conn.close()

def get_connected_server():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT ip, port, username, status FROM servers WHERE status='connected' LIMIT 1")
    server = c.fetchone()
    conn.close()
    return server

# توابع جدید مدیریت تانل
def save_tunnel(name, transport, tunnel_port, token, config_dict):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    # فعلا فرض می‌کنیم فقط یک تانل داریم، پس قبلی‌ها را پاک می‌کنیم (یا می‌توانید چند تانلی کنید)
    c.execute("DELETE FROM tunnels") 
    c.execute("INSERT INTO tunnels (name, transport, tunnel_port, token, config_json) VALUES (?, ?, ?, ?, ?)",
              (name, transport, tunnel_port, token, config_json))
    conn.commit()
    conn.close()

def get_tunnel():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels LIMIT 1")
    tunnel = c.fetchone()
    conn.close()
    return tunnel

def delete_tunnels():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tunnels")
    conn.commit()
    conn.close()