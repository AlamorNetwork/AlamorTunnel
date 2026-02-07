import sqlite3
import json
import os
from core.backup_manager import save_tunnel_config, delete_tunnel_config, load_all_configs

DB_PATH = "alamor.db"

# --- توابع کمکی (Standalone) ---
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row 
    return conn

def get_connected_server():
    """
    این تابع باید بیرون از کلاس باشد تا ssh_manager بتواند آن را ایمپورت کند.
    """
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM servers LIMIT 1")
        res = c.fetchone()
        conn.close()
        if res:
            return tuple(res)
        return None
    except Exception:
        return None

# --- کلاس اصلی Database ---
class Database:
    def __init__(self):
        self.init_db()

    def get_db(self):
        return get_db_connection()

    def init_db(self):
        conn = self.get_db()
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
        
        # --- بازیابی هوشمند از فایل‌ها ---
        try:
            c.execute("SELECT count(*) FROM tunnels")
            if c.fetchone()[0] == 0:
                print("Restoring tunnels from file backups...")
                backups = load_all_configs()
                for b in backups:
                    try:
                        name = b.get('name', f"Recovered-{b.get('transport', 'tunnel')}-{b.get('port', '0')}")
                        transport = b.get('transport', 'unknown')
                        port = str(b.get('port', '0'))
                        token = b.get('token', '')
                        config = b.get('config', '{}')
                        
                        if not isinstance(config, str):
                            config = json.dumps(config)
                            
                        c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
                                  (name, transport, port, token, config, 'active'))
                    except Exception as e:
                        print(f"Skipping corrupt backup: {e}")
                conn.commit()
        except Exception as e:
            print(f"Database Init Error: {e}")
            
        conn.close()

    # --- مدیریت کاربر ---
    def check_user(self, username, password):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        res = c.fetchone()
        conn.close()
        return res

    def update_password(self, new_pass):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE username='admin'", (new_pass,))
        conn.commit()
        conn.close()

    # --- مدیریت سرور ---
    def add_server(self, ip, user, password, port):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("DELETE FROM servers")
        c.execute("INSERT INTO servers VALUES (?, ?, ?, ?)", (ip, user, password, port))
        conn.commit()
        conn.close()

    def remove_server(self):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("DELETE FROM servers")
        conn.commit()
        conn.close()

    # --- مدیریت تانل‌ها ---
    def get_tunnels(self):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM tunnels ORDER BY id DESC")
        res = c.fetchall()
        conn.close()
        return res

    def get_tunnel(self, tunnel_id):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM tunnels WHERE id=?", (tunnel_id,))
        res = c.fetchone()
        conn.close()
        return res

    def add_tunnel(self, name, transport, port, token, config_dict, **kwargs):
        conn = self.get_db()
        c = conn.cursor()
        config_json = json.dumps(config_dict)
        
        c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
                  (name, transport, str(port), token, config_json, 'active'))
        tunnel_id = c.lastrowid
        conn.commit()
        conn.close()
        
        save_tunnel_config({
            'id': tunnel_id, 'name': name, 'transport': transport, 
            'port': str(port), 'token': token, 'config': config_dict
        })
        return tunnel_id

    def delete_tunnel(self, tunnel_id):
        tunnel = self.get_tunnel(tunnel_id)
        if tunnel:
            delete_tunnel_config(tunnel_id)
            conn = self.get_db()
            c = conn.cursor()
            c.execute("DELETE FROM tunnels WHERE id=?", (tunnel_id,))
            conn.commit()
            conn.close()
            return True
        return False

    def update_tunnel(self, tunnel_id, name, transport, port, config_dict):
        conn = self.get_db()
        c = conn.cursor()
        config_json = json.dumps(config_dict)
        c.execute("UPDATE tunnels SET name=?, transport=?, port=?, config=? WHERE id=?", 
                  (name, transport, str(port), config_json, tunnel_id))
        conn.commit()
        conn.close()
        
        save_tunnel_config({
            'id': tunnel_id, 'name': name, 'transport': transport, 
            'port': str(port), 'token': '', 'config': config_dict
        })

# --- توابع Wrapper برای سازگاری با کدهای قدیمی (app.py و routes) ---

def init_db():
    # ساختن اینستنس، خود به خود init_db را صدا می‌زند
    Database()

def check_user(username, password):
    return Database().check_user(username, password)

def update_password(new_pass):
    Database().update_password(new_pass)

def add_server(ip, user, password, port):
    Database().add_server(ip, user, password, port)

def remove_server():
    Database().remove_server()

def get_all_tunnels():
    return Database().get_tunnels()

def get_tunnel_by_id(tid):
    return Database().get_tunnel(tid)

def add_tunnel(name, transport, port, token, config_dict):
    return Database().add_tunnel(name, transport, port, token, config_dict)

def delete_tunnel_by_id(tid):
    return Database().delete_tunnel(tid)

def update_tunnel_config(tid, name, transport, port, config_dict):
    return Database().update_tunnel(tid, name, transport, port, config_dict)