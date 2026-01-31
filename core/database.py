import sqlite3
import random
import string
import json
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "alamor.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # جداول پایه
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servers 
                 (id INTEGER PRIMARY KEY, ip TEXT UNIQUE, port INTEGER DEFAULT 22, username TEXT DEFAULT 'root', status TEXT DEFAULT 'disconnected')''')
    
    # جدول تانل‌ها (برای مدیریت چندین تانل)
    c.execute('''CREATE TABLE IF NOT EXISTS tunnels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        transport TEXT,
        tunnel_port INTEGER,
        token TEXT,
        config_json TEXT,
        status TEXT DEFAULT 'active'
    )''')
    
    conn.commit()
    conn.close()

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
                 ON CONFLICT(ip) DO UPDATE SET status=excluded.status, port=excluded.port""", 
              (ip, port, username, status))
    conn.commit()
    conn.close()

def get_connected_server():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT ip, port, username, status FROM servers WHERE status='connected' LIMIT 1")
    server = c.fetchone()
    conn.close()
    return server

# --- مدیریت تانل‌ها ---

def add_tunnel(name, transport, tunnel_port, token, config_dict):
    """اضافه کردن تانل جدید به لیست"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    c.execute("INSERT INTO tunnels (name, transport, tunnel_port, token, config_json, status) VALUES (?, ?, ?, ?, ?, ?)",
              (name, transport, tunnel_port, token, config_json, 'active'))
    conn.commit()
    conn.close()

def get_all_tunnels():
    """دریافت همه تانل‌ها"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels ORDER BY id DESC")
    tunnels = c.fetchall()
    conn.close()
    return tunnels

def get_tunnel_by_id(tunnel_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels WHERE id=?", (tunnel_id,))
    tunnel = c.fetchone()
    conn.close()
    return tunnel

def delete_tunnel_by_id(tunnel_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tunnels WHERE id=?", (tunnel_id,))
    conn.commit()
    conn.close()