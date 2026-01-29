import sqlite3
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "alamor.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول کاربران
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
    # جدول تنظیمات
    c.execute('''CREATE TABLE IF NOT EXISTS settings 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

def create_initial_user():
    """یک یوزر ادمین با پسورد رندوم می‌سازد اگر وجود نداشته باشد"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        # تولید پسورد رندوم ۸ رقمی
        chars = string.ascii_letters + string.digits
        raw_pass = ''.join(random.choice(chars) for i in range(10))
        hashed_pass = generate_password_hash(raw_pass)
        
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', hashed_pass))
        conn.commit()
        print(f"\n[+] AlamorTunnel Setup Complete!")
        print(f"[+] Username: admin")
        print(f"[+] Password: {raw_pass}")
        print(f"[!] Please save this password immediately.\n")
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