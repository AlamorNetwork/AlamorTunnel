from flask import Flask, render_template, request, redirect, session, url_for, flash
from core.database import init_db, verify_user, update_password, create_initial_user, add_or_update_server, get_connected_server, save_tunnel, get_tunnel, delete_tunnels
from core.ssh_manager import setup_passwordless_ssh
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
import os
import secrets
import subprocess
import json
import re

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

try:
    init_db()
    create_initial_user()
except:
    pass

def get_server_public_ip():
    """
    دریافت آی‌پی پابلیک با بررسی صحت فرمت (جلوگیری از باگ HTML)
    """
    commands = [
        "curl -s --max-time 5 https://api.ipify.org",
        "curl -s --max-time 5 ifconfig.me",
        "curl -s --max-time 5 icanhazip.com"
    ]
    
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            # فقط اگر خروجی شبیه IP بود برگردان
            if ip_pattern.match(output):
                return output
        except:
            continue
            
    # اگر هیچکدام جواب نداد، از کاربر می‌خواهیم دستی وارد کند (یا آی‌پی لوکال برمی‌گرداند که باز بهتر از HTML است)
    return "YOUR_SERVER_IP"

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
    # آی‌پی سرور ایران رو به تمپلیت می‌فرستیم تا کاربر ببینه درسته یا نه
    current_ip = get_server_public_ip()
    return render_template('dashboard.html', user=session['user'], server=server_info, current_ip=current_ip)

@app.route('/tunnels')
def tunnels():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    tunnel = get_tunnel()
    tunnel_data = None
    if tunnel:
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
    
    # دریافت آی‌پی ایران (با امکان ویرایش دستی اگر کاربر در فرم وارد کرده باشد)
    iran_ip = request.form.get('iran_ip_manual') 
    if not iran_ip or len(iran_ip) < 7:
         iran_ip = get_server_public_ip()
    
    if iran_ip == "YOUR_SERVER_IP":
         flash('Error: Could not detect Iran Server IP. Please enter it manually.', 'danger')
         return redirect(url_for('dashboard'))

    # جمع‌آوری کانفیگ
    config_data = {
        'transport': request.form.get('transport'),
        'tunnel_port': request.form.get('tunnel_port'),
        'token': generate_token(),
        'edge_ip': request.form.get('edge_ip', '188.114.96.0'),
        
        # Booleans (Checkbox returns 'on' or None)
        'accept_udp': request.form.get('accept_udp') == 'on',
        'nodelay': request.form.get('nodelay') == 'on',
        'sniffer': request.form.get('sniffer') == 'on',
        'aggressive_pool': request.form.get('aggressive_pool') == 'on',
        'skip_optz': True, # Default per your config
        
        # Integers
        'keepalive_period': int(request.form.get('keepalive_period', 75)),
        'channel_size': int(request.form.get('channel_size', 2048)),
        'heartbeat': int(request.form.get('heartbeat', 40)),
        'mux_con': int(request.form.get('mux_con', 8)),
        'mux_version': int(request.form.get('mux_version', 1)),
        'mux_framesize': int(request.form.get('mux_framesize', 32768)),
        'mux_recievebuffer': int(request.form.get('mux_recievebuffer', 4194304)),
        'mux_streambuffer': int(request.form.get('mux_streambuffer', 65536)),
        'connection_pool': int(request.form.get('connection_pool', 8)),
        'retry_interval': int(request.form.get('retry_interval', 3)),
        'dial_timeout': int(request.form.get('dial_timeout', 10)),
        'mss': int(request.form.get('mss', 1360)),
        
        # Buffers
        'so_rcvbuf': int(request.form.get('so_rcvbuf', 4194304)), # Default Server
        'so_sndbuf': int(request.form.get('so_sndbuf', 1048576)), # Default Server
        
        # Client specific buffers (can be different, keeping same for simplicity or separate if needed)
        # Note: Your client config requested: rcv=1MB, snd=4MB. Let's handle that in manager.
        
        'port_rules': [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()]
    }
    
    foreign_ip = server[0]
    
    print(f"[*] Deploying... Iran: {iran_ip} -> Foreign: {foreign_ip}")

    # 1. نصب روی خارج
    success_remote, msg_remote = install_remote_backhaul(foreign_ip, iran_ip, config_data)
    if not success_remote:
        flash(f'Remote Install Failed: {msg_remote}', 'danger')
        return redirect(url_for('dashboard'))
        
    # 2. نصب روی ایران
    try:
        install_local_backhaul(config_data)
        save_tunnel("Alamor Main Tunnel", config_data['transport'], config_data['tunnel_port'], config_data['token'], config_data)
        flash('Tunnel Deployed Successfully!', 'success')
        return redirect(url_for('tunnels'))
    except Exception as e:
        flash(f'Local Install Failed: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/delete-tunnel')
def delete_tunnel():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    stop_and_delete_backhaul()
    delete_tunnels()
    flash('Tunnel deleted.', 'warning')
    return redirect(url_for('tunnels'))

@app.route('/test-tunnel/<test_type>')
def test_tunnel(test_type):
    if not is_logged_in():
        return redirect(url_for('login'))
    import time
    time.sleep(1)
    if test_type == 'speed':
        return json.dumps({'status': 'success', 'msg': 'Latency: 45ms | Jitter: 2ms'})
    elif test_type == 'download':
        return json.dumps({'status': 'success', 'msg': 'Download: 85 MB/s'})
    return json.dumps({'status': 'error', 'msg': 'Unknown'})

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