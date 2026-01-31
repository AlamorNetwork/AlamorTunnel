from flask import Flask, redirect, url_for
# تغییر مهم: حذف create_initial_user از ایمپورت‌ها
from core.database import init_db
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.tunnels import tunnels_bp
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# راه‌اندازی دیتابیس (ساخت جداول و یوزر ادمین)
init_db()

# ثبت بلوپرینت‌ها (مسیرها)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(tunnels_bp)

# مسیر ریشه -> ریدایرکت به دشبورد
@app.route('/')
def root():
    return redirect(url_for('dashboard.index'))

if __name__ == '__main__':
    # اجرا روی پورت 80
    app.run(host='0.0.0.0', port=80, debug=True)