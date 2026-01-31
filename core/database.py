# AlamorTunnel/routes/dashboard.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from core.database import get_connected_server, add_server, remove_server
from core.ssh_manager import verify_ssh_connection
from routes.auth import login_required

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    try:
        server = get_connected_server()
        # server[0] is IP if exists
        server_ip = server[0] if server else None
        return render_template('dashboard.html', server_ip=server_ip)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return render_template('dashboard.html', server_ip=None)

@dashboard_bp.route('/connect-server', methods=['POST'])
@login_required
def connect_server():
    ip = request.form.get('ip')
    user = request.form.get('username', 'root')
    password = request.form.get('password')
    try:
        port = int(request.form.get('port', 22))
    except:
        port = 22

    if not ip or not password:
        flash('IP and Password are required.', 'warning')
        return redirect(url_for('dashboard.index'))

    # تست اتصال قبل از ذخیره
    if verify_ssh_connection(ip, user, password, port):
        add_server(ip, user, password, port)
        flash('Foreign Server Connected Successfully!', 'success')
    else:
        flash('Connection Failed! Check IP, Password, or SSH Port.', 'danger')
        
    return redirect(url_for('dashboard.index'))

@dashboard_bp.route('/disconnect-server')
@login_required
def disconnect_server():
    try:
        remove_server()
        flash('Server disconnected.', 'info')
    except Exception as e:
        flash(f'Error disconnecting: {e}', 'danger')
        
    return redirect(url_for('dashboard.index'))