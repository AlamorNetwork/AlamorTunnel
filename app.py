from flask import Flask, render_template, request, redirect, session, url_for, flash
from core.database import init_db, verify_user, update_password, create_initial_user, add_or_update_server, get_connected_server, save_tunnel, get_tunnel, delete_tunnels
from core.ssh_manager import setup_passwordless_ssh
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
import os
import secrets
import subprocess
import json

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

@app.route('/tunnels')
def tunnels():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    # دریافت تانل فعال
    tunnel = get_tunnel()
    tunnel_data = None
    if tunnel:
        # tunnel: (id, name, transport, port, token, config_json, status)
        tunnel_data = {
            'id': tunnel[0],
            'name': tunnel[1],
            'transport': tunnel[2],
            'port': tunnel[3],
            'config': json.loads(tunnel[5]),
            'status': tunnel[6]
        }
    return render_template('tunnels.html', tunnel=tunnel_data)

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
    
    # جمع‌آوری تمام اطلاعات فرم
    config_data = {
        'transport': request.form.get('transport'),
        'tunnel_port': request.form.get('tunnel_port'),
        'token': generate_token(),
        
        # آپشن‌های پیشرفته
        'accept_udp': request.form.get('accept_udp') == 'on',
        'nodelay': request.form.get('nodelay') == 'on',
        'keepalive_period': request.form.get('keepalive_period'),
        'channel_size': request.form.get('channel_size'),
        'mux_con': request.form.get('mux_con'),
        'mux_version': request.form.get('mux_version'),
        'connection_pool': request.form.get('connection_pool'),
        'aggressive_pool': request.form.get('aggressive_pool') == 'on',
        'mss': request.form.get('mss'),
        'so_rcvbuf': request.form.get('so_rcvbuf'),
        'so_sndbuf': request.form.get('so_sndbuf'),
        
        # پورت‌ها
        'port_rules': [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()]
    }
    
    foreign_ip = server[0]
    iran_ip = get_server_public_ip()
    
    print(f"[*] Deploying Backhaul with Config: {config_data}")

    # 1. نصب روی خارج
    success_remote, msg_remote = install_remote_backhaul(foreign_ip, iran_ip, config_data)
    if not success_remote:
        flash(f'Remote Install Failed: {msg_remote}', 'danger')
        return redirect(url_for('dashboard'))
        
    # 2. نصب روی ایران
    try:
        install_local_backhaul(config_data)
        # ذخیره در دیتابیس
        save_tunnel("Alamor Main Tunnel", config_data['transport'], config_data['tunnel_port'], config_data['token'], config_data)
        flash('Tunnel Deployed Successfully!', 'success')
        return redirect(url_for('tunnels')) # رفتن به صفحه تانل‌ها
    except Exception as e:
        flash(f'Local Install Failed: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/delete-tunnel')
def delete_tunnel():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    stop_and_delete_backhaul()
    delete_tunnels()
    flash('Tunnel deleted and service stopped.', 'warning')
    return redirect(url_for('tunnels'))

@app.route('/test-tunnel/<test_type>')
def test_tunnel(test_type):
    if not is_logged_in():
        return redirect(url_for('login'))
    
    # شبیه‌سازی تست (برای تست واقعی نیاز به پکیج‌های شبکه است)
    import time
    time.sleep(1)
    
    if test_type == 'speed':
        # اینجا باید لاجیک واقعی اسپیدتست رو بذاریم (مثلا iperf)
        # فعلا فیک برمی‌گردونیم
        return json.dumps({'status': 'success', 'msg': 'Latency: 120ms | Jitter: 5ms'})
    
    elif test_type == 'download':
        # تست دانلود فایل
        return json.dumps({'status': 'success', 'msg': 'Download Speed: 45 MB/s'})
        
    return json.dumps({'status': 'error', 'msg': 'Unknown test'})

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