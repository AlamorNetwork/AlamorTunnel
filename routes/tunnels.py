from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
# ایمپورت کلاس Database و Wrapperها
from core.database import Database, get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config
from core.ssh_manager import SSHManager
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import install_hysteria_server_remote, install_hysteria_client_local, generate_pass
from core.gost_manager import install_gost_server_remote, install_gost_client_local
from core.traffic import get_traffic_stats, run_advanced_speedtest
from core.tasks import task_queue, init_task, task_status
from routes.auth import login_required
from core.ssl_manager import set_root_tunnel 
import psutil
from core.config_loader import load_config
import os
import subprocess
import json
import re
import threading
import time
import uuid

tunnels_bp = Blueprint('tunnels', __name__)

# --- WORKER FUNCTION ---
def run_task_in_background(task_id, func, args):
    try:
        task_status[task_id] = {'progress': 5, 'status': 'running', 'log': 'Starting process...'}
        for percent, log_msg in func(*args):
            task_status[task_id] = {
                'progress': percent, 
                'status': 'running', 
                'log': log_msg
            }
            time.sleep(0.5)
        task_status[task_id] = {'progress': 100, 'status': 'completed', 'log': 'Installation Successfully Completed!'}
    except Exception as e:
        print(f"Task Failed: {e}")
        task_status[task_id] = {'progress': 100, 'status': 'error', 'log': f"Error: {str(e)}"}

# --- CLEANUP HELPER (سیستم حذف هوشمند) ---
def get_cleanup_commands(protocol, is_remote=False):
    """دستورات لینوکسی برای حذف سرویس‌ها"""
    base_dir = "/root/alamor" if is_remote else "/root/AlamorTunnel"
    commands = []
    service_name = ""
    
    if protocol == 'hysteria2' or protocol == 'hysteria':
        service_name = "hysteria-server" if is_remote else "hysteria-client"
        config_file = f"{base_dir}/bin/config.yaml" if is_remote else f"{base_dir}/bin/hysteria_client.yaml"
    elif 'backhaul' in protocol:
        service_name = "backhaul"
        config_file = f"{base_dir}/bin/backhaul.toml"
    elif 'rathole' in protocol:
        service_name = "rathole"
        config_file = f"{base_dir}/bin/rathole.toml"
    elif 'gost' in protocol:
        service_name = "gost"
        config_file = f"{base_dir}/bin/config.json"

    if service_name:
        commands.append(f"systemctl stop {service_name}")
        commands.append(f"systemctl disable {service_name}")
        commands.append(f"rm /etc/systemd/system/{service_name}.service")
        commands.append("systemctl daemon-reload")
        # کشتن پروسه‌های جامانده
        commands.append(f"pkill -f {service_name}")
        commands.append(f"rm -f {config_file}")

    return "; ".join(commands)

# --- HELPERS ---
def get_server_public_ip():
    providers = [
        "curl -s --max-time 3 https://api.ipify.org",
        "curl -s --max-time 3 https://icanhazip.com",
        "curl -s --max-time 3 http://ifconfig.me/ip"
    ]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    for cmd in providers:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output): return output
        except: continue
    return "127.0.0.1"

# --- GENERATORS ---
def process_backhaul(server_ip, iran_ip, config):
    yield 10, f"Connecting to Remote Server ({server_ip})..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Install Failed: {msg}")
    
    yield 50, "Remote Configured. Installing Local..."
    try:
        install_local_backhaul(config)
    except Exception as e: raise Exception(f"Local Install Failed: {e}")
    
    if config['transport'] in ['ws', 'wss', 'wsmux', 'wssmux']:
        yield 70, "Binding Tunnel to Domain Root (443)..."
        ok, nginx_msg = set_root_tunnel(config['tunnel_port'])
        if ok:
            config['ws_path'] = "/"
            config['domain_url'] = f"https://{load_config().get('panel_domain')}"
        else:
            yield 75, f"Warning: Nginx Error ({nginx_msg})"
            
    yield 90, "Local Configured. Saving to DB..."
    add_tunnel("Backhaul Tunnel", config['transport'], config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

def process_gost(server_ip, config):
    yield 20, "Installing Gost on Remote..."
    success, msg = install_gost_server_remote(server_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Configuring Local Gost..."
    install_gost_client_local(server_ip, config)
    yield 90, "Saving Tunnel..."
    add_tunnel(f"GOST-{config['tunnel_port']}", "gost", config['client_port'], "N/A", config)
    yield 100, "Done!"

def process_hysteria(server_ip, config):
    yield 10, "Installing Hysteria on Remote..."
    success, msg = install_hysteria_server_remote(server_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Configuring Local Client..."
    install_hysteria_client_local(server_ip, config)
    yield 90, "Saving..."
    add_tunnel(f"Hysteria2-{config['tunnel_port']}", "hysteria", config['tunnel_port'], config['password'], config)
    yield 100, "Done!"

def process_rathole(server_ip, iran_ip, config):
    yield 10, "Installing Rathole on Remote..."
    success, msg = install_remote_rathole(server_ip, iran_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Configuring Local Rathole..."
    install_local_rathole(config)
    yield 90, "Saving..."
    add_tunnel(f"Rathole-{config['tunnel_port']}", "rathole", config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

# --- ROUTES ---

@tunnels_bp.route('/api/task_status/<task_id>')
@login_required
def get_task_status_route(task_id):
    return jsonify(task_status.get(task_id, {'progress': 0, 'status': 'queued'}))

@tunnels_bp.route('/start-install/<protocol>', methods=['POST'])
@login_required
def start_install(protocol):
    server = get_connected_server()
    if not server: return jsonify({'status': 'error', 'message': 'No remote server connected!'})
    
    config = request.form.to_dict()
    task_id = str(uuid.uuid4())
    init_task(task_id)

    target_func = None
    args = ()

    if protocol == 'backhaul':
        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        config['token'] = generate_token()
        raw_ports = request.form.get('port_rules', '').strip()
        config['port_rules'] = [l.strip() for l in raw_ports.split('\n') if l.strip()]
        
        bool_fields = ['accept_udp', 'nodelay', 'sniffer', 'skip_optz', 'aggressive_pool']
        for f in bool_fields: config[f] = request.form.get(f) == 'on'
            
        int_fields = ['keepalive_period', 'heartbeat', 'mux_con', 'channel_size', 'mss', 'so_rcvbuf', 'so_sndbuf', 'mux_version', 'mux_framesize', 'mux_recievebuffer', 'mux_streambuffer', 'web_port', 'dial_timeout', 'retry_interval', 'connection_pool', 'tunnel_port']
        for f in int_fields:
            if config.get(f) and config[f].isdigit(): config[f] = int(config[f])
        
        config['tls_cert'] = '/root/certs/server.crt'
        config['tls_key'] = '/root/certs/server.key'
        target_func = process_backhaul
        args = (server[0], iran_ip, config)

    elif protocol == 'gost':
        target_func = process_gost
        args = (server[0], config)
        
    elif protocol == 'hysteria':
        raw = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw.split(',') if p.strip().isdigit()]
        config['password'] = config.get('password') or generate_pass()
        config['obfs_pass'] = config.get('obfs_pass') or generate_pass()
        target_func = process_hysteria
        args = (server[0], config)
        
    elif protocol == 'rathole':
        iran_ip = get_server_public_ip()
        raw = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw.split(',') if p.strip().isdigit()]
        config['token'] = config.get('token') or generate_token()
        config['ipv6'] = request.form.get('ipv6') == 'on'
        config['nodelay'] = request.form.get('nodelay') == 'on'
        target_func = process_rathole
        args = (server[0], iran_ip, config)

    if target_func:
        thread = threading.Thread(target=run_task_in_background, args=(task_id, target_func, args))
        thread.start()
        return jsonify({'status': 'started', 'task_id': task_id})
    
    return jsonify({'status': 'error', 'message': 'Unknown protocol'})

@tunnels_bp.route('/run-speedtest/<int:tunnel_id>')
@login_required
def run_tunnel_speedtest_route(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    result = run_advanced_speedtest()
    result['status'] = 'ok'
    return jsonify(result)

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

# --- DELETE TUNNEL (اصلاح شده + پاکسازی کامل) ---
@tunnels_bp.route('/delete/<int:tunnel_id>', methods=['POST'])
@login_required
def delete_tunnel_route(tunnel_id):
    try:
        # 1. گرفتن اطلاعات تانل
        # استفاده از کلاس Database برای دسترسی مطمئن
        db = Database()
        tunnel = db.get_tunnel(tunnel_id)
        
        if not tunnel:
            return jsonify({'status': 'error', 'message': 'Tunnel not found'})

        protocol = tunnel['transport']
        
        # 2. پاک‌سازی سمت ایران (Local)
        local_cmd = get_cleanup_commands(protocol, is_remote=False)
        print(f"Cleaning Local: {local_cmd}")
        subprocess.run(local_cmd, shell=True, executable='/bin/bash')

        # 3. پاک‌سازی سمت خارج (Remote)
        # دریافت اطلاعات سرور از دیتابیس سرورها
        server = get_connected_server()
        if server:
            server_ip, ssh_user, ssh_pass, ssh_port = server
            remote_cmd = get_cleanup_commands(protocol, is_remote=True)
            print(f"Cleaning Remote {server_ip}: {remote_cmd}")
            
            ssh = SSHManager()
            ssh.run_remote_command(server_ip, ssh_user, ssh_pass, remote_cmd, ssh_port)

        # 4. حذف از دیتابیس
        db.delete_tunnel(tunnel_id)
        os.system("systemctl daemon-reload")
        
        return jsonify({'status': 'ok'})
        
    except Exception as e:
        print(f"Delete Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@tunnels_bp.route('/tunnel/edit/<int:tunnel_id>')
@login_required
def edit_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel:
        flash('Tunnel not found!', 'danger')
        return redirect(url_for('tunnels.list_tunnels'))
    
    try:
        config = json.loads(tunnel['config'])
    except:
        config = {}
        
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