from flask import Flask, render_template, request, redirect, session, url_for, flash
from core.database import init_db, verify_user, update_password, create_initial_user, add_or_update_server, get_connected_server
from core.ssh_manager import setup_passwordless_ssh
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token
import os
import secrets
import subprocess

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

try:
    init_db()
    create_initial_user()
except:
    pass

def get_server_public_ip():
    try:
        return subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    except:
        return "YOUR_IRAN_IP"

def is_logged_in():
    return 'user' in session

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if verify_user(username, password):
            session['user'] = username
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect(url_for('login'))
    server_info = get_connected_server()
    return render_template('dashboard.html', user=session['user'], server=server_info)

@app.route('/connect-server', methods=['POST'])
def connect_server():
    if not is_logged_in():
        return redirect(url_for('login'))
    ip = request.form.get('ip')
    password = request.form.get('password')
    port = request.form.get('port', 22)
    
    success, message = setup_passwordless_ssh(ip, password, port)
    if success:
        add_or_update_server(ip, port, 'root', 'connected')
        flash(f'Success: {message}', 'success')
    else:
        flash(f'Failed: {message}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/install-backhaul', methods=['POST'])
def install_backhaul():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    server = get_connected_server()
    if not server:
        flash('Error: No connected foreign server found.', 'danger')
        return redirect(url_for('dashboard'))
    
    # دریافت اطلاعات از فرم
    transport = request.form.get('transport', 'tcp')
    
    foreign_ip = server[0]
    iran_ip = get_server_public_ip()
    
    # پورت‌ها (فعلا هاردکد، بعدا می‌توان از فرم گرفت)
    local_port = 8080
    remote_port = 8080
    tunnel_port = 3080
    token = generate_token()
    
    print(f"[*] Starting Install. Transport: {transport} | Iran: {iran_ip} | Foreign: {foreign_ip}")

    # 1. نصب روی سرور خارج
    success_remote, msg_remote = install_remote_backhaul(foreign_ip, iran_ip, tunnel_port, token, transport)
    
    if not success_remote:
        flash(f'Remote Install Failed: {msg_remote}', 'danger')
        return redirect(url_for('dashboard'))
        
    # 2. نصب روی سرور ایران
    try:
        install_local_backhaul(local_port, remote_port, tunnel_port, token, transport)
        flash(f'Tunnel Established ({transport.upper()})! Local Port: {local_port}', 'success')
    except Exception as e:
        flash(f'Local Install Failed: {str(e)}', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not is_logged_in():
        return redirect(url_for('login'))
    if request.method == 'POST':
        if 'new_password' in request.form:
            new_pass = request.form['new_password']
            update_password(session['user'], new_pass)
            flash('Password updated', 'success')
    return render_template('settings.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)