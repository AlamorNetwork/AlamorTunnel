import sqlite3
import json
import os
import datetime

DB_PATH = "alamor.db"

class Database:
    def __init__(self):
        self.init_db()

    def get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_db()
        c = conn.cursor()
        
        # 1. Users Table
        c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
        
        # 2. Servers Table (Added ssh_key)
        c.execute('''CREATE TABLE IF NOT EXISTS servers (
            ip TEXT PRIMARY KEY, 
            user TEXT, 
            password TEXT, 
            ssh_key TEXT, 
            port INTEGER
        )''')
        
        # 3. Tunnels Table (Added traffic stats)
        c.execute('''CREATE TABLE IF NOT EXISTS tunnels (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT, 
            transport TEXT, 
            port TEXT, 
            token TEXT, 
            config TEXT, 
            status TEXT DEFAULT 'active',
            total_rx INTEGER DEFAULT 0,
            total_tx INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # 4. Traffic History Table (For Charts)
        c.execute('''CREATE TABLE IF NOT EXISTS traffic_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tunnel_id INTEGER,
            date DATE,
            rx INTEGER DEFAULT 0,
            tx INTEGER DEFAULT 0,
            UNIQUE(tunnel_id, date)
        )''')
        
        # Default Admin
        c.execute("SELECT * FROM users WHERE username='admin'")
        if not c.fetchone():
            c.execute("INSERT INTO users VALUES ('admin', 'admin')")
        
        conn.commit()
        conn.close()

    # --- Server Management ---
    def add_server(self, ip, user, password, ssh_key, port):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("DELETE FROM servers") # Single server mode for now
        c.execute("INSERT INTO servers VALUES (?, ?, ?, ?, ?)", (ip, user, password, ssh_key, port))
        conn.commit()
        conn.close()

    def get_connected_server(self):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM servers LIMIT 1")
        res = c.fetchone()
        conn.close()
        return tuple(res) if res else None

    def remove_server(self):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("DELETE FROM servers")
        conn.commit()
        conn.close()

    # --- User Management ---
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

    # --- Tunnel Management ---
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

    def add_tunnel(self, name, transport, port, token, config_dict):
        conn = self.get_db()
        c = conn.cursor()
        config_json = json.dumps(config_dict)
        c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", 
                  (name, transport, str(port), token, config_json, 'active'))
        tunnel_id = c.lastrowid
        conn.commit()
        conn.close()
        return tunnel_id

    def delete_tunnel(self, tunnel_id):
        conn = self.get_db()
        c = conn.cursor()
        c.execute("DELETE FROM tunnels WHERE id=?", (tunnel_id,))
        conn.commit()
        conn.close()
        return True

    def update_tunnel(self, tunnel_id, name, transport, port, config_dict):
        conn = self.get_db()
        c = conn.cursor()
        config_json = json.dumps(config_dict)
        c.execute("UPDATE tunnels SET name=?, transport=?, port=?, config=? WHERE id=?", 
                  (name, transport, str(port), config_json, tunnel_id))
        conn.commit()
        conn.close()

    # --- Traffic Logging ---
    def update_traffic_usage(self, tunnel_id, rx_increment, tx_increment):
        conn = self.get_db()
        c = conn.cursor()
        today = datetime.date.today()
        
        # Update Total
        c.execute("UPDATE tunnels SET total_rx = total_rx + ?, total_tx = total_tx + ? WHERE id=?", 
                  (rx_increment, tx_increment, tunnel_id))
        
        # Update Daily History
        c.execute("INSERT OR IGNORE INTO traffic_history (tunnel_id, date, rx, tx) VALUES (?, ?, 0, 0)", 
                  (tunnel_id, today))
        c.execute("UPDATE traffic_history SET rx = rx + ?, tx = tx + ? WHERE tunnel_id=? AND date=?", 
                  (rx_increment, tx_increment, tunnel_id, today))
        
        conn.commit()
        conn.close()

# Wrappers
def init_db(): Database()
def get_connected_server(): return Database().get_connected_server()
def add_server(ip, user, password, ssh_key, port): Database().add_server(ip, user, password, ssh_key, port)
def remove_server(): Database().remove_server()
def check_user(u, p): return Database().check_user(u, p)
def update_password(p): Database().update_password(p)
def get_all_tunnels(): return Database().get_tunnels()
def get_tunnel_by_id(tid): return Database().get_tunnel(tid)
def add_tunnel(name, transport, port, token, config): return Database().add_tunnel(name, transport, port, token, config)
def delete_tunnel_by_id(tid): return Database().delete_tunnel(tid)
def update_tunnel_config(tid, name, transport, port, config): return Database().update_tunnel(tid, name, transport, port, config)