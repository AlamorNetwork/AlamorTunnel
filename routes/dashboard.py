from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from core.database import get_connected_server, add_or_update_server
from core.ssh_manager import setup_passwordless_ssh
import subprocess
import re

dashboard_bp = Blueprint('dashboard', __name__)

def is_logged_in():
    return 'user' in session

def get_server_public_ip():
    commands = ["curl -s --max-time 5 ifconfig.me", "curl -s --max-time 5 api.ipify.org"]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output): return output
        except: continue
    return "YOUR_SERVER_IP"

@dashboard_bp.route('/dashboard')
def index():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    server_info = get_connected_server()
    current_ip = get_server_public_ip()
    return render_template('dashboard.html', user=session['user'], server=server_info, current_ip=current_ip)

@dashboard_bp.route('/connect-server', methods=['POST'])
def connect_server():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    ip = request.form.get('ip')
    password = request.form.get('password')
    port = request.form.get('port', 22)
    
    success, message = setup_passwordless_ssh(ip, password, port)
    
    if success:
        add_or_update_server(ip, port, 'root', 'connected')
        flash(f'Connection Established: {message}', 'success')
    else:
        flash(f'Connection Failed: {message}', 'danger')
        
    return redirect(url_for('dashboard.index'))