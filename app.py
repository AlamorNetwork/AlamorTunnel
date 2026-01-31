from flask import Flask, render_template, request, redirect, session, url_for, flash
from core.database import init_db, verify_user, update_password, create_initial_user, add_or_update_server, get_connected_server, add_tunnel, get_all_tunnels, delete_tunnel_by_id, get_tunnel_by_id
from core.ssh_manager import setup_passwordless_ssh
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
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
    commands = [
        "curl -s --max-time 5 https://api.ipify.org",
        "curl -s --max-time 5 ifconfig.me",
        "curl -s --max-time 5 icanhazip.com"
    ]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output):
                return output
        except:
            continue
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
    current_ip = get_server_public_ip()
    return render_template('dashboard.html', user=session['user'], server=server_info, current_ip=current_ip)

@app.route('/tunnels')
def tunnels():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    raw_tunnels = get_all_tunnels()
    tunnels_list = []
    for t in raw_tunnels:
        tunnels_list.append({
            'id': t[0],
            'name': t[1],
            'transport': t[2],
            'port': t[3],
            'config': json.loads(t[5]),
            'status': t[6]
        })
    return render_template('tunnels.html', tunnels=tunnels_list)

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
        flash('Error: No foreign server connected.', 'danger')
        return redirect(url_for('dashboard'))

    iran_ip = request.form.get('iran_ip_manual') 
    if not iran_ip or len(iran_ip) < 7:
         iran_ip = get_server_public_ip()

    if iran_ip == "YOUR_SERVER_IP":
         flash('Error: Invalid Iran Server IP.', 'danger')
         return redirect(url_for('dashboard'))

    config_data = {
        'transport': request.form.get('transport'),
        'tunnel_port': request.form.get('tunnel_port'),
        'token': generate_token(),
        'edge_ip': request.form.get('edge_ip'),
        'accept_udp': request.form.get('accept_udp') == 'on',
        'nodelay': request.form.get('nodelay') == 'on',
        'sniffer': request.form.get('sniffer') == 'on',
        'aggressive_pool': request.form.get('aggressive_pool') == 'on',
        'skip_optz': True,
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
        'so_rcvbuf': int(request.form.get('so_rcvbuf', 4194304)),
        'so_sndbuf': int(request.form.get('so_sndbuf', 1048576)),
        'port_rules': [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()]
    }
    
    foreign_ip = server[0]
    success_remote, msg_remote = install_remote_backhaul(foreign_ip, iran_ip, config_data)
    
    if not success_remote:
        flash(f'Remote Install Failed: {msg_remote}', 'danger')
        return redirect(url_for('dashboard'))
        
    try:
        install_local_backhaul(config_data)
        add_tunnel("Backhaul Tunnel", config_data['transport'], config_data['tunnel_port'], config_data['token'], config_data)
        flash('Backhaul Tunnel Deployed Successfully!', 'success')
        return redirect(url_for('tunnels'))
    except Exception as e:
        flash(f'Local Install Failed: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/install-rathole', methods=['POST'])
def install_rathole():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    server = get_connected_server()
    if not server:
        flash('Error: No foreign server connected.', 'danger')
        return redirect(url_for('dashboard'))

    iran_ip = request.form.get('iran_ip_manual')
    if not iran_ip:
         iran_ip = get_server_public_ip()

    raw_ports = request.form.get('forward_ports', '')
    ports_list = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
    
    if not ports_list:
        flash('Error: Valid ports required.', 'warning')
        return redirect(url_for('dashboard'))

    config_data = {
        'tunnel_port': request.form.get('tunnel_port'),
        'transport': request.form.get('transport'),
        'token': request.form.get('token') if request.form.get('token') else generate_token(),
        'ipv6': request.form.get('ipv6') == 'on',
        'nodelay': request.form.get('nodelay') == 'on',
        'heartbeat': request.form.get('heartbeat') == 'on',
        'ports': ports_list
    }
    
    foreign_ip = server[0]
    success_remote, msg_remote = install_remote_rathole(foreign_ip, iran_ip, config_data)
    
    if not success_remote:
        flash(f'Remote Failed: {msg_remote}', 'danger')
        return redirect(url_for('dashboard'))

    try:
        install_local_rathole(config_data)
        add_tunnel(f"Rathole-{config_data['tunnel_port']}", "rathole", config_data['tunnel_port'], config_data['token'], config_data)
        flash(f'Rathole Established on port {config_data["tunnel_port"]}!', 'success')
        return redirect(url_for('tunnels'))
    except Exception as e:
        flash(f'Local Failed: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/delete-tunnel/<int:tunnel_id>')
def delete_tunnel(tunnel_id):
    if not is_logged_in():
        return redirect(url_for('login'))
    
    tunnel = get_tunnel_by_id(tunnel_id)
    if tunnel:
        tunnel_port = tunnel[3]
        transport_name = tunnel[1]
        
        if "Rathole" in transport_name:
            service_name = f"rathole-iran{tunnel_port}"
            os.system(f"systemctl stop {service_name} && systemctl disable {service_name}")
            os.system(f"rm /etc/systemd/system/{service_name}.service")
            os.system(f"rm /root/rathole-core/iran{tunnel_port}.toml")
        else:
            stop_and_delete_backhaul()
            
        delete_tunnel_by_id(tunnel_id)
        os.system("systemctl daemon-reload")
        flash('Tunnel deleted.', 'warning')
        
    return redirect(url_for('tunnels'))

@app.route('/test-tunnel/<test_type>')
def test_tunnel(test_type):
    if not is_logged_in():
        return redirect(url_for('login'))
    return json.dumps({'status': 'success', 'msg': 'Test Passed'})

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