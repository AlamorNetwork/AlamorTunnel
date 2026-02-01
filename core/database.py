import sqlite3
import json
import os
from core.backup_manager import save_tunnel_config, delete_tunnel_config, load_all_configs, save_tunnel_config

DB_PATH = "alamor.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # جداول
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servers (ip TEXT PRIMARY KEY, user TEXT, password TEXT, port INTEGER)''')
    
    # ساخت جدول تانل‌ها (اگر وجود نداشت)
    c.execute('''CREATE TABLE IF NOT EXISTS tunnels 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT, 
                  transport TEXT, 
                  port TEXT, 
                  token TEXT, 
                  config TEXT,
                  status TEXT DEFAULT 'active')''')
    
    # ادمین پیش‌فرض
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES ('admin', 'admin')")
    
    conn.commit()
    
    # --- MAGIC: همگام‌سازی فایل‌ها با دیتابیس ---
    # اگر دیتابیس خالی بود یا ریست شده بود، از فایل‌ها می‌خواند
    c.execute("SELECT count(*) FROM tunnels")
    count = c.fetchone()[0]
    
    if count == 0:
        print("[System] Database is empty. Restoring from backups...")
        backups = load_all_configs()
        for b in backups:
            # تبدیل دیکشنری کانفیگ به رشته JSON برای دیتابیس
            config_str = json.dumps(b['config'])
            c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
                      (b['name'], b['transport'], b['port'], b['token'], config_str, 'active'))
            print(f"[Restore] Restored tunnel: {b['name']}")
        conn.commit()
        
    conn.close()

# --- توابع کاربر و سرور (بدون تغییر) ---
def check_user(username, password):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def add_server(ip, user, password, port):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM servers") 
    c.execute("INSERT INTO servers (ip, user, password, port) VALUES (?, ?, ?, ?)", (ip, user, password, port))
    conn.commit()
    conn.close()

def get_connected_server():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM servers LIMIT 1")
    data = c.fetchone()
    conn.close()
    return data

def remove_server():
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM servers")
    conn.commit()
    conn.close()

# --- توابع تانل (آپدیت شده با فایل) ---
def add_tunnel(name, transport, port, token, config_dict):
    conn = get_db()
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    
    # 1. ذخیره در دیتابیس
    c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
              (name, transport, str(port), token, config_json, 'active'))
    tunnel_id = c.lastrowid # گرفتن آی‌دی جدید
    conn.commit()
    conn.close()
    
    # 2. ذخیره در فایل (بکاپ)
    backup_data = {
        'id': tunnel_id,
        'name': name,
        'transport': transport,
        'port': str(port),
        'token': token,
        'config': config_dict # ذخیره به صورت دیکشنری در فایل برای خوانایی
    }
    save_tunnel_config(backup_data)

def get_all_tunnels():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data

def get_tunnel_by_id(tid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels WHERE id=?", (tid,))
    data = c.fetchone()
    conn.close()
    return data

def delete_tunnel_by_id(tid):
    # ابتدا اطلاعات را می‌گیریم تا بدانیم کدام فایل را پاک کنیم
    tunnel = get_tunnel_by_id(tid)
    if tunnel:
        transport = tunnel['transport']
        port = tunnel['port']
        
        # 1. حذف از فایل
        delete_tunnel_config(transport, port)
        
        # 2. حذف از دیتابیس
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
    
    # آپدیت فایل بکاپ
    backup_data = {
        'id': tid,
        'name': name,
        'transport': transport,
        'port': str(port),
        'token': '', # توکن ممکن است در ادیت تغییر نکند یا نیاز به بازخوانی باشد
        'config': config_dict
    }
    save_tunnel_config(backup_data)