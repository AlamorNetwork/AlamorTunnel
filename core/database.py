import sqlite3
import json
import os
from core.backup_manager import save_tunnel_config, delete_tunnel_config, load_all_configs

DB_PATH = "alamor.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # ساخت جداول
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servers (ip TEXT PRIMARY KEY, user TEXT, password TEXT, port INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tunnels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, transport TEXT, port TEXT, token TEXT, config TEXT, status TEXT DEFAULT 'active')''')
    
    # یوزر پیش‌فرض
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES ('admin', 'admin')")
    
    conn.commit()
    
    # --- بازیابی هوشمند از فایل‌ها (Fix KeyError) ---
    try:
        c.execute("SELECT count(*) FROM tunnels")
        if c.fetchone()[0] == 0:
            print("Restoring tunnels from file backups...")
            backups = load_all_configs()
            for b in backups:
                try:
                    # استفاده از .get() برای جلوگیری از ارور در صورت ناقص بودن بکاپ
                    name = b.get('name', f"Recovered-{b.get('transport', 'tunnel')}-{b.get('port', '0')}")
                    transport = b.get('transport', 'unknown')
                    port = str(b.get('port', '0'))
                    token = b.get('token', '')
                    config = b.get('config', '{}')
                    
                    # اطمینان از اینکه کانفیگ استرینگ است
                    if not isinstance(config, str):
                        config = json.dumps(config)
                        
                    c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
                              (name, transport, port, token, config, 'active'))
                    print(f"Restored tunnel: {name}")
                except Exception as e:
                    print(f"Skipping corrupt backup file: {e}")
            conn.commit()
    except Exception as e:
        print(f"Database Init Error: {e}")
        
    conn.close()

# --- توابع کاربر ---
def check_user(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    res = c.fetchone()
    conn.close()
    return res

def update_password(new_pass):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET password=? WHERE username='admin'", (new_pass,))
    conn.commit()
    conn.close()

# --- توابع سرور ---
def add_server(ip, user, password, port):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM servers")
    c.execute("INSERT INTO servers VALUES (?, ?, ?, ?)", (ip, user, password, port))
    conn.commit(); conn.close()

def get_connected_server():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM servers LIMIT 1")
    res = c.fetchone(); conn.close()
    return res

def remove_server():
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM servers")
    conn.commit(); conn.close()

def get_all_tunnels():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM tunnels ORDER BY id DESC")
    res = c.fetchall(); conn.close()
    return res

def get_tunnel_by_id(tid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM tunnels WHERE id=?", (tid,))
    res = c.fetchone(); conn.close()
    return res

# --- توابع مهم تانل با پشتیبانی فایل ---
def add_tunnel(name, transport, port, token, config_dict):
    conn = get_db()
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    
    # 1. دیتابیس
    c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
              (name, transport, str(port), token, config_json, 'active'))
    tunnel_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # 2. فایل (برای بکاپ)
    save_tunnel_config({
        'id': tunnel_id, 'name': name, 'transport': transport, 
        'port': str(port), 'token': token, 'config': config_dict
    })

def delete_tunnel_by_id(tid):
    tunnel = get_tunnel_by_id(tid)
    if tunnel:
        delete_tunnel_config(tunnel['transport'], tunnel['port'])
        
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM tunnels WHERE id=?", (tid,))
        conn.commit()
        conn.close()

def update_tunnel_config(tid, name, transport, port, config_dict):
    conn = get_db()
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    c.execute("UPDATE tunnels SET name=?, transport=?, port=?, config=? WHERE id=?", 
              (name, transport, str(port), config_json, tid))
    conn.commit()
    conn.close()
    
    # آپدیت فایل
    save_tunnel_config({
        'id': tid, 'name': name, 'transport': transport, 
        'port': str(port), 'token': '', 'config': config_dict
    })