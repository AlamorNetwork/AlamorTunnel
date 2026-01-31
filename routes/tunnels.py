from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from core.database import get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
import json
import os
import subprocess
import socket
import time
import re

tunnels_bp = Blueprint('tunnels', __name__)

def is_logged_in(): return 'user' in session

def get_server_public_ip():
    commands = ["curl -s --max-time 5 ifconfig.me", "curl -s --max-time 5 api.ipify.org"]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output): return output
        except: continue
    return "YOUR_SERVER_IP"

# --- LIST TUNNELS ---
@tunnels_bp.route('/tunnels')
def list_tunnels():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    raw_tunnels = get_all_tunnels()
    tunnels_list = []
    
    for t in raw_tunnels:
        try:
            config = json.loads(t[5])
        except:
            config = {}
            
        tunnels_list.append({
            'id': t[0],
            'name': t[1],
            'transport': t[2],
            'port': t[3],
            'token': t[4],  # Token is index 4
            'config': config,
            'status': t[6]
        })
        
    return render_template('tunnels.html', tunnels=tunnels_list)

# --- EDIT TUNNEL ---
@tunnels_bp.route('/edit-tunnel/<int:tunnel_id>', methods=['GET', 'POST'])
def edit_tunnel(tunnel_id):
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel:
        flash('Tunnel not found.', 'danger')
        return redirect(url_for('tunnels.list_tunnels'))

    # استخراج اطلاعات فعلی
    try:
        current_config = json.loads(tunnel[5])
    except:
        current_config = {}
        
    transport_type = tunnel[2]
    
    if request.method == 'POST':
        server = get_connected_server()
        if not server:
            flash('Foreign server not connected.', 'danger')
            return redirect(url_for('dashboard.index'))

        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        
        # کپی و آپدیت کانفیگ
        new_config = current_config.copy()
        new_config['tunnel_port'] = request.form.get('tunnel_port')
        new_config['transport'] = request.form.get('transport')
        
        # تنظیمات مشترک
        new_config['nodelay'] = request.form.get('nodelay') == 'on'
        
        # منطق ذخیره سازی بر اساس نوع تانل
        if 'rathole' in transport_type or transport_type in ['tcp', 'udp'] and 'port_rules' not in request.form:
             # RATHOLE UPDATE
             raw_ports = request.form.get('forward_ports', '')
             new_config['ports'] = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
             new_config['ipv6'] = request.form.get('ipv6') == 'on'
             new_config['heartbeat'] = request.form.get('heartbeat') == 'on'
             
             install_remote_rathole(server[0], iran_ip, new_config)
             install_local_rathole(new_config)
             update_tunnel_config(tunnel_id, f"Rathole-{new_config['tunnel_port']}", "rathole", new_config['tunnel_port'], new_config)

        else:
             # BACKHAUL UPDATE
             new_config['edge_ip'] = request.form.get('edge_ip')
             new_config['port_rules'] = [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()]
             new_config['mux_version'] = int(request.form.get('mux_version', 1))
             # دریافت سایر فیلدهای عددی اگر در فرم باشند
             if request.form.get('heartbeat'): new_config['heartbeat'] = int(request.form.get('heartbeat'))
             
             install_remote_backhaul(server[0], iran_ip, new_config)
             install_local_backhaul(new_config)
             update_tunnel_config(tunnel_id, "Backhaul Tunnel", new_config['transport'], new_config['tunnel_port'], new_config)

        flash('Tunnel Updated & Restarted Successfully!', 'success')
        return redirect(url_for('tunnels.list_tunnels'))

    return render_template('edit_tunnel.html', tunnel=tunnel, config=current_config, current_ip=get_server_public_ip())

# --- REAL TESTS ---
@tunnels_bp.route('/perform-test/<int:tunnel_id>/<test_type>')
def perform_test(tunnel_id, test_type):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel: return jsonify({'status': 'error', 'msg': 'Tunnel not found'})
    
    target_port = int(tunnel[3])
    target_ip = "127.0.0.1"
    
    if test_type == 'speed':
        try:
            start_time = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            result = s.connect_ex((target_ip, target_port))
            end_time = time.time()
            s.close()
            
            if result == 0:
                latency = round((end_time - start_time) * 1000, 2)
                return jsonify({'status': 'success', 'msg': f'Latency: {latency}ms', 'raw': latency})
            else:
                return jsonify({'status': 'error', 'msg': 'Port Unreachable'})
        except Exception as e:
            return jsonify({'status': 'error', 'msg': str(e)})

    elif test_type == 'download':
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((target_ip, target_port))
            s.sendall(b'PING') # Small packet to check stream health
            s.close()
            return jsonify({'status': 'success', 'msg': 'Stream Healthy'})
        except:
            return jsonify({'status': 'error', 'msg': 'Connection Failed'})

    return jsonify({'status': 'error', 'msg': 'Invalid Test'})

# --- INSTALL ROUTES ---

@tunnels_bp.route('/install-backhaul', methods=['POST'])
def install_backhaul():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    server = get_connected_server()
    if not server:
        flash('No foreign server connected.', 'danger')
        return redirect(url_for('dashboard.index'))

    iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
    
    if iran_ip == "YOUR_SERVER_IP":
         flash('Error: Invalid Iran Server IP.', 'danger')
         return redirect(url_for('dashboard.index'))

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

    success_remote, msg_remote = install_remote_backhaul(server[0], iran_ip, config_data)
    if not success_remote:
        flash(f'Remote Error: {msg_remote}', 'danger')
        return redirect(url_for('dashboard.index'))

    try:
        install_local_backhaul(config_data)
        add_tunnel("Backhaul Tunnel", config_data['transport'], config_data['tunnel_port'], config_data['token'], config_data)
        flash('Backhaul Tunnel Created!', 'success')
        return redirect(url_for('tunnels.list_tunnels'))
    except Exception as e:
        flash(f'Local Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@tunnels_bp.route('/install-rathole', methods=['POST'])
def install_rathole():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    server = get_connected_server()
    if not server:
        flash('No foreign server connected.', 'danger')
        return redirect(url_for('dashboard.index'))

    iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
    raw_ports = request.form.get('forward_ports', '')
    ports_list = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]

    if not ports_list:
        flash('Valid ports required.', 'warning')
        return redirect(url_for('dashboard.index'))

    config_data = {
        'tunnel_port': request.form.get('tunnel_port'),
        'transport': request.form.get('transport'),
        'token': request.form.get('token') if request.form.get('token') else generate_token(),
        'ipv6': request.form.get('ipv6') == 'on',
        'nodelay': request.form.get('nodelay') == 'on',
        'heartbeat': request.form.get('heartbeat') == 'on',
        'ports': ports_list
    }

    success_remote, msg_remote = install_remote_rathole(server[0], iran_ip, config_data)
    if not success_remote:
        flash(f'Remote Error: {msg_remote}', 'danger')
        return redirect(url_for('dashboard.index'))

    try:
        install_local_rathole(config_data)
        add_tunnel(f"Rathole-{config_data['tunnel_port']}", "rathole", config_data['tunnel_port'], config_data['token'], config_data)
        flash('Rathole Tunnel Created!', 'success')
        return redirect(url_for('tunnels.list_tunnels'))
    except Exception as e:
        flash(f'Local Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
def delete_tunnel(tunnel_id):
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    tunnel = get_tunnel_by_id(tunnel_id)
    if tunnel:
        if "rathole" in tunnel[2] or "Rathole" in tunnel[1]: 
            svc = f"rathole-iran{tunnel[3]}"
            os.system(f"systemctl stop {svc} && systemctl disable {svc} && rm /etc/systemd/system/{svc}.service")
            os.system(f"rm /root/rathole-core/iran{tunnel[3]}.toml")
        else:
            stop_and_delete_backhaul()
            
        delete_tunnel_by_id(tunnel_id)
        os.system("systemctl daemon-reload")
        flash('Tunnel Deleted.', 'success')
        
    return redirect(url_for('tunnels.list_tunnels'))