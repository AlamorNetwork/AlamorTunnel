from flask import Flask, redirect, url_for, session
from core.database import init_db, create_initial_user
import secrets
import os

# ایمپورت کردن بلوپرینت‌ها
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
from routes.settings import settings_bp

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# راه اندازی اولیه دیتابیس
try:
    init_db()
    create_initial_user()
except:
    pass

# ثبت بلوپرینت‌ها
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tunnels_bp)
app.register_blueprint(settings_bp)

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)