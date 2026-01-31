import sqlite3
import os
import json

DB_PATH = "alamor.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servers (ip TEXT PRIMARY KEY, user TEXT, password TEXT, port INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tunnels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, transport TEXT, port TEXT, token TEXT, config TEXT, status TEXT DEFAULT 'active')''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users VALUES ('admin', 'admin')")
    conn.commit()
    conn.close()

# --- Server Functions ---
def add_server(ip, user, password, port):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM servers")
    c.execute("INSERT INTO servers (ip, user, password, port) VALUES (?, ?, ?, ?)", (ip, user, password, port))
    conn.commit()
    conn.close()

def remove_server():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM servers")
    conn.commit()
    conn.close()

def get_connected_server():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM servers LIMIT 1")
    data = c.fetchone()
    conn.close()
    return data

# --- Tunnel Functions ---
def add_tunnel(name, transport, port, token, config_dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    c.execute("INSERT INTO tunnels (name, transport, port, token, config, status) VALUES (?, ?, ?, ?, ?, ?)", (name, transport, str(port), token, config_json, 'active'))
    conn.commit()
    conn.close()

def get_all_tunnels():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data

def get_tunnel_by_id(tid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM tunnels WHERE id=?", (tid,))
    data = c.fetchone()
    conn.close()
    return data

def delete_tunnel_by_id(tid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tunnels WHERE id=?", (tid,))
    conn.commit()
    conn.close()

def update_tunnel_config(tid, name, transport, port, config_dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    c.execute("UPDATE tunnels SET name=?, transport=?, port=?, config=? WHERE id=?", (name, transport, str(port), config_json, tid))
    conn.commit()
    conn.close()

# --- User Functions ---
def check_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def get_admin_user():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username='admin'")
    data = c.fetchone()
    conn.close()
    return data

def update_password(new_pass):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET password=? WHERE username='admin'", (new_pass,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()