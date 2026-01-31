from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from core.database import get_connected_server, add_server, remove_server, get_admin_user
from core.ssh_manager import verify_ssh_connection

dashboard_bp = Blueprint('dashboard', __name__)

def is_logged_in():
    return 'user' in session

@dashboard_bp.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('auth.login'))
    
    # اصلاح باگ نمایش وضعیت: همیشه از دیتابیس چک کن
    server = get_connected_server()
    server_ip = server[0] if server else None
    
    return render_template('index.html', server_ip=server_ip)

@dashboard_bp.route('/connect-server', methods=['POST'])
def connect_server():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    ip = request.form.get('ip')
    user = request.form.get('username')
    password = request.form.get('password')
    port = request.form.get('port', 22)

    if verify_ssh_connection(ip, user, password, port):
        # ذخیره در دیتابیس
        add_server(ip, user, password, port)
        flash('Connected to Foreign Server successfully!', 'success')
    else:
        flash('Connection Failed! Check IP/Password.', 'danger')
        
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/disconnect-server')
def disconnect_server():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    remove_server()
    flash('Server disconnected.', 'info')
    return redirect(url_for('dashboard.index'))