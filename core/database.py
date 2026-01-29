import sqlite3
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "alamor.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS servers (id INTEGER PRIMARY KEY, ip TEXT UNIQUE, port INTEGER DEFAULT 22, username TEXT DEFAULT 'root', status TEXT DEFAULT 'disconnected')''')
    conn.commit()
    conn.close()

def create_initial_user():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        chars = string.ascii_letters + string.digits
        raw_pass = ''.join(random.choice(chars) for i in range(12)) # 12 کاراکتر برای امنیت بیشتر
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