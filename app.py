# AlamorTunnel/app.py
from flask import Flask, redirect, url_for
from core.database import init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# راه اندازی دیتابیس
init_db()

# ثبت مسیرها
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tunnels_bp)

@app.route('/')
def root():
    return redirect(url_for('dashboard.index'))

if __name__ == '__main__':
    # تغییر پورت به 5050
    print("🚀 AlamorPanel started on http://0.0.0.0:5050")
    app.run(host='0.0.0.0', port=5050, debug=True)