from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import Database, get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config
from core.ssh_manager import SSHManager
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import install_hysteria_server_remote, install_hysteria_client_local, generate_pass
from core.gost_manager import install_gost_server_remote, install_gost_client_local
from core.traffic import get_traffic_stats, run_advanced_speedtest
from core.tasks import task_queue, init_task, task_status
from routes.auth import login_required
import threading
import time
import uuid
import subprocess
import os
import json

tunnels_bp = Blueprint('tunnels', __name__)

def generic_error(log_message):
    print(f"!!! SYSTEM ERROR !!! : {log_message}")
    return jsonify({
        'status': 'error', 
        'message': 'Operation failed. Please check server logs (journalctl -u alamor) for details.'
    })

def run_task_in_background(task_id, func, args):
    try:
        task_status[task_id] = {'progress': 5, 'status': 'running', 'log': 'Starting process...'}
        for percent, log_msg in func(*args):
            task_status[task_id] = {'progress': percent, 'status': 'running', 'log': log_msg}
            time.sleep(0.5)
        task_status[task_id] = {'progress': 100, 'status': 'completed', 'log': 'Completed Successfully!'}
    except Exception as e:
        print(f"Task Failed: {e}")
        task_status[task_id] = {'progress': 100, 'status': 'error', 'log': f"Error: {str(e)}"}

def get_server_public_ip():
    try:
        return subprocess.check_output("curl -s https://api.ipify.org", shell=True).decode().strip()
    except:
        return "127.0.0.1"

# --- Install Logic Generators ---
def process_backhaul(server_ip, iran_ip, config):
    yield 10, f"Connecting to Remote ({server_ip})..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Install Failed: {msg}")
    
    yield 50, "Remote Configured. Installing Local..."
    success, msg = install_local_backhaul(config)
    if not success: raise Exception(f"Local Install Failed: {msg}")
    
    yield 90, "Saving to Database..."
    add_tunnel(config['name'], "backhaul", config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

def process_hysteria(server_ip, config):
    yield 10, "Installing Hysteria Remote..."
    success, msg = install_hysteria_server_remote(server_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Configuring Local Client..."
    install_hysteria_client_local(server_ip, config)
    yield 90, "Saving..."
    add_tunnel(f"Hysteria2-{config['tunnel_port']}", "hysteria", config['tunnel_port'], config['password'], config)
    yield 100, "Done!"

def process_rathole(server_ip, iran_ip, config):
    yield 10, "Installing Rathole Remote..."
    success, msg = install_remote_rathole(server_ip, iran_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Configuring Local Rathole..."
    install_local_rathole(config)
    yield 90, "Saving..."
    add_tunnel(f"Rathole-{config['tunnel_port']}", "rathole", config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

def process_gost(server_ip, config):
    yield 20, "Installing Gost Remote..."
    success, msg = install_gost_server_remote(server_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Configuring Local Gost..."
    install_gost_client_local(server_ip, config)
    yield 90, "Saving Tunnel..."
    add_tunnel(f"GOST-{config['tunnel_port']}", "gost", config['client_port'], "N/A", config)
    yield 100, "Done!"

# --- ROUTES ---

@tunnels_bp.route('/start-install/<protocol>', methods=['POST'])
@login_required
def start_install(protocol):
    try:
        server = get_connected_server()
        if not server:
            return jsonify({'status': 'error', 'message': 'No remote server connected!'})
        
        # Unpack server info (ip, user, pass, key, port)
        server_ip, ssh_user, ssh_pass, ssh_key, ssh_port = server
        
        config = request.form.to_dict()
        config['ssh_ip'] = server_ip
        config['ssh_user'] = ssh_user
        config['ssh_pass'] = ssh_pass
        config['ssh_key'] = ssh_key
        config['ssh_port'] = ssh_port
        
        task_id = str(uuid.uuid4())
        init_task(task_id)
        
        target_func = None
        args = ()

        if protocol == 'backhaul':
            iran_ip = get_server_public_ip()
            config['token'] = generate_token()
            
            # Parsing Ports
            raw_ports = request.form.get('port_rules', '').strip()
            config['port_rules'] = [l.strip() for l in raw_ports.split('\n') if l.strip()]
            
            # Parsing Booleans (Checkbox logic)
            bool_fields = ['accept_udp', 'nodelay', 'sniffer', 'aggressive_pool']
            for f in bool_fields: config[f] = (request.form.get(f) == 'on')
            
            # Parsing Integers
            int_fields = [
                'tunnel_port', 'connection_pool', 'mux_con', 'mux_version', 
                'mux_framesize', 'mux_recievebuffer', 'mux_streambuffer',
                'keepalive_period', 'heartbeat', 'channel_size', 'web_port',
                'dial_timeout', 'retry_interval'
            ]
            for f in int_fields:
                if config.get(f) and str(config[f]).isdigit(): config[f] = int(config[f])

            target_func = process_backhaul
            args = (server_ip, iran_ip, config)

        elif protocol == 'hysteria':
            raw = config.get('forward_ports', '')
            config['ports'] = [p.strip() for p in raw.split(',') if p.strip().isdigit()]
            config['password'] = config.get('password') or generate_pass()
            config['obfs_pass'] = config.get('obfs_pass') or generate_pass()
            target_func = process_hysteria
            args = (server_ip, config)
            
        elif protocol == 'rathole':
            iran_ip = get_server_public_ip()
            raw = config.get('forward_ports', '')
            config['ports'] = [p.strip() for p in raw.split(',') if p.strip().isdigit()]
            config['token'] = config.get('token') or generate_token()
            config['ipv6'] = (request.form.get('ipv6') == 'on')
            config['nodelay'] = (request.form.get('nodelay') == 'on')
            target_func = process_rathole
            args = (server_ip, iran_ip, config)

        elif protocol == 'gost':
             target_func = process_gost
             args = (server_ip, config)

        if target_func:
            threading.Thread(target=run_task_in_background, args=(task_id, target_func, args)).start()
            return jsonify({'status': 'started', 'task_id': task_id})
        
        return jsonify({'status': 'error', 'message': 'Unknown Protocol'})

    except Exception as e:
        return generic_error(str(e))

@tunnels_bp.route('/api/task_status/<task_id>')
@login_required
def get_task_status_route(task_id):
    status = task_status.get(task_id)
    if not status:
        return jsonify({'progress': 0, 'status': 'not_found', 'log': 'Task not found'})
    return jsonify(status)

@tunnels_bp.route('/delete/<int:tunnel_id>', methods=['POST'])
@login_required
def delete_tunnel_route(tunnel_id):
    try:
        db = Database()
        tunnel = db.get_tunnel(tunnel_id)
        if not tunnel: return jsonify({'status': 'error', 'message': 'Not found'})
        
        transport = tunnel['transport']
        port = tunnel['port']
        service_name = ""

        if transport == 'backhaul':
            service_name = f"backhaul-client-{port}"
        elif transport == 'rathole':
             service_name = f"rathole-iran{port}"
        elif transport == 'hysteria':
            service_name = "hysteria-client"
        elif transport == 'gost':
             service_name = "gost-client"

        if service_name:
            os.system(f"systemctl stop {service_name}")
            os.system(f"systemctl disable {service_name}")
            os.system(f"rm /etc/systemd/system/{service_name}.service")
        
        db.delete_tunnel(tunnel_id)
        os.system("systemctl daemon-reload")
        return jsonify({'status': 'ok'})
    except Exception as e:
        return generic_error(str(e))

# (Other routes list_tunnels, server_speedtest, etc remain the same)
@tunnels_bp.route('/tunnels')
@login_required
def list_tunnels():
    tunnels = get_all_tunnels()
    return render_template('tunnels.html', tunnels=tunnels)

@tunnels_bp.route('/stats/<int:tunnel_id>')
@login_required
def tunnel_stats(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel: return jsonify({'error': 'Not found'})
    try: port = int(tunnel['port'])
    except: port = 0
    transport = tunnel['transport']
    proto = 'udp' if 'hysteria' in transport else 'tcp'
    rx, tx = get_traffic_stats(port, proto)
    return jsonify({'rx': round(rx/1024/1024, 2), 'tx': round(tx/1024/1024, 2)})

@tunnels_bp.route('/run-speedtest/<int:tunnel_id>')
@login_required
def run_tunnel_speedtest_route(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    target_ip = None
    if tunnel:
        try:
            config = json.loads(tunnel['config'])
            connected_server = get_connected_server()
            if connected_server:
                target_ip = connected_server[0]
        except: pass
    result = run_advanced_speedtest(target_ip=target_ip)
    result['tunnel_name'] = tunnel['name'] if tunnel else "Unknown"
    result['status'] = 'ok'
    return jsonify(result)

@tunnels_bp.route('/server-speedtest')
@login_required
def server_speedtest():
    try:
        result = run_advanced_speedtest()
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@tunnels_bp.route('/tunnel/edit/<int:tunnel_id>')
@login_required
def edit_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel:
        flash('Tunnel not found!', 'danger')
        return redirect(url_for('tunnels.list_tunnels'))
    try: config = json.loads(tunnel['config'])
    except: config = {}
    return render_template('edit_tunnel.html', tunnel=tunnel, config=config)

@tunnels_bp.route('/tunnel/update/<int:tunnel_id>', methods=['POST'])
@login_required
def update_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel:
        flash('Tunnel not found!', 'danger')
        return redirect(url_for('tunnels.list_tunnels'))
    config = request.form.to_dict()
    try:
        current_config = json.loads(tunnel['config'])
        current_config.update(config) 
        update_tunnel_config(tunnel_id, tunnel['name'], tunnel['transport'], tunnel['port'], current_config)
        flash('Tunnel configuration updated (Service restart required).', 'success')
    except Exception as e:
        flash(f'Update failed: {str(e)}', 'danger')
    return redirect(url_for('tunnels.list_tunnels'))