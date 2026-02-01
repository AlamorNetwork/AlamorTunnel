from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import (get_connected_server, add_tunnel, get_all_tunnels, 
                           get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config)
from core.backhaul_manager import (install_local_backhaul, install_remote_backhaul, 
                                   generate_token, stop_and_delete_backhaul)
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import (install_hysteria_server_remote, 
                                   install_hysteria_client_local, generate_pass)
from core.slipstream_manager import (install_slipstream_server_remote, 
                                     install_slipstream_client_local)
from core.slipstream_manager import install_slipstream_server_remote_gen, install_slipstream_client_local_gen
from routes.auth import login_required
# ایمپورت حیاتی از فایل جدید
from core.tasks import task_queue, init_task
import json
import os
import subprocess
import uuid
import re

tunnels_bp = Blueprint('tunnels', __name__)
def process_slipstream(server_ip, config):
    yield 5, "Initializing Remote Build Environment..."
    
    # --- Remote Install ---
    # لاگ‌ها را زنده می‌خوانیم
    for log in install_slipstream_server_remote_gen(server_ip, config):
        # تخمین پیشرفت بر اساس متن لاگ‌ها
        progress = 10
        if "Updating submodules" in log: progress = 15
        elif "Compiling" in log: progress = 20 # چون بیلد طولانی است
        elif "Finished release" in log: progress = 45
        elif "Server Service Started" in log: progress = 50
        
        # نمایش لاگ زنده به کاربر
        # محدود کردن طول لاگ برای جلوگیری از بهم ریختن UI
        clean_log = log[-50:] if len(log) > 50 else log
        yield progress, f"Remote: {clean_log}"
        
    yield 50, "Starting Local Build (Takes 5-10 mins)..."
    
    # --- Local Install ---
    for log in install_slipstream_client_local_gen(server_ip, config):
        progress = 50
        if "Compiling" in log: progress = 60
        elif "Finished" in log: progress = 90
        
        clean_log = log[-50:] if len(log) > 50 else log
        yield progress, f"Local: {clean_log}"
    
    yield 95, "Finalizing Config..."
    add_tunnel(f"Slipstream-{config['tunnel_port']}", "slipstream", config['client_port'], "N/A", config)
    yield 100, "Installation Complete!"def get_server_public_ip():
    commands = ["curl -s --max-time 3 ifconfig.me", "curl -s --max-time 3 api.ipify.org"]
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if len(output) < 20: return output
        except: continue
    return "YOUR_IRAN_IP"

# --- GENERATOR FUNCTIONS (مراحل نصب) ---

def process_hysteria(server_ip, config):
    yield 10, "Installing Remote Hysteria Server..."
    os.system("apt-get install -y ntpdate && ntpdate pool.ntp.org")
    
    success, msg = install_hysteria_server_remote(server_ip, config)
    if not success: raise Exception(f"Remote Install Failed: {msg}")
    
    yield 50, "Configuring Local Client..."
    install_hysteria_client_local(server_ip, config)
    
    yield 90, "Saving Configuration..."
    add_tunnel(f"Hysteria2-{config['tunnel_port']}", "hysteria", config['tunnel_port'], config['password'], config)
    yield 100, "Done"

def process_slipstream(server_ip, config):
    yield 10, "Building Remote Server (Rust)..."
    success, msg = install_slipstream_server_remote(server_ip, config)
    if not success: raise Exception(f"Remote Build Failed: {msg}")
    
    yield 40, "Building Local Client (This takes time)..."
    install_slipstream_client_local(server_ip, config)
    
    yield 90, "Finalizing..."
    add_tunnel(f"Slipstream-{config['tunnel_port']}", "slipstream", config['client_port'], "N/A", config)
    yield 100, "Done"

def process_rathole(server_ip, iran_ip, config):
    yield 10, "Configuring Remote Rathole..."
    success, msg = install_remote_rathole(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
    
    yield 60, "Configuring Local Rathole..."
    install_local_rathole(config)
    
    yield 90, "Saving..."
    add_tunnel(f"Rathole-{config['tunnel_port']}", "rathole", config['tunnel_port'], config['token'], config)
    yield 100, "Done"

def process_backhaul(server_ip, iran_ip, config):
    yield 10, "Setting up Remote Backhaul..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
    
    yield 60, "Setting up Local Backhaul..."
    install_local_backhaul(config)
    
    yield 90, "Saving..."
    add_tunnel("Backhaul Tunnel", config['transport'], config['tunnel_port'], config['token'], config)
    yield 100, "Done"

# --- ASYNC INSTALL ROUTE ---

@tunnels_bp.route('/start-install/<protocol>', methods=['POST'])
@login_required
def start_install(protocol):
    server = get_connected_server()
    if not server:
        return jsonify({'status': 'error', 'message': 'Foreign server not connected'})

    # دریافت داده‌های فرم
    form_data = request.form.to_dict()
    config = form_data.copy()
    
    # ایجاد ID برای تسک
    task_id = str(uuid.uuid4())
    init_task(task_id) # جلوگیری از Undefined در لحظه اول

    if protocol == 'hysteria':
        raw_ports = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
        config['password'] = config.get('password') or generate_pass()
        config['obfs_pass'] = config.get('obfs_pass') or generate_pass()
        
        task_queue.put((task_id, process_hysteria, (server[0], config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    elif protocol == 'slipstream':
        if not config.get('domain'): config['domain'] = 'dl.google.com'
        if not config.get('dest_port'): config['dest_port'] = '8080'
        if not config.get('client_port'): config['client_port'] = '8443'
        
        task_queue.put((task_id, process_slipstream, (server[0], config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    elif protocol == 'rathole':
        iran_ip = get_server_public_ip()
        raw_ports = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
        config['token'] = config.get('token') or generate_token()
        config['ipv6'] = request.form.get('ipv6') == 'on'
        config['nodelay'] = request.form.get('nodelay') == 'on'
        config['heartbeat'] = request.form.get('heartbeat') == 'on'
        
        task_queue.put((task_id, process_rathole, (server[0], iran_ip, config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    elif protocol == 'backhaul':
        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        config['token'] = generate_token()
        config['port_rules'] = [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()]
        
        # مدیریت چک‌باکس‌ها
        for field in ['accept_udp', 'nodelay', 'sniffer', 'skip_optz', 'aggressive_pool']:
            config[field] = request.form.get(field) == 'on'
            
        # مدیریت اعداد
        int_fields = ['keepalive_period', 'heartbeat', 'mux_con', 'channel_size', 'mss', 
                      'so_rcvbuf', 'so_sndbuf', 'client_so_rcvbuf', 'client_so_sndbuf', 
                      'connection_pool', 'retry_interval', 'dial_timeout', 'web_port']
        for field in int_fields:
            if config.get(field): 
                try: config[field] = int(config[field])
                except: pass
            
        config['tls_cert'] = '/root/certs/server.crt'
        config['tls_key'] = '/root/certs/server.key'

        task_queue.put((task_id, process_backhaul, (server[0], iran_ip, config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    return jsonify({'status': 'error', 'message': 'Unknown protocol'})

# --- LIST & MANAGEMENT ROUTES ---

@tunnels_bp.route('/tunnels')
@login_required
def list_tunnels():
    try:
        raw_tunnels = get_all_tunnels()
        tunnels_list = []
        for t in raw_tunnels:
            try: config = json.loads(t[5])
            except: config = {}
            tunnels_list.append({
                'id': t[0], 'name': t[1], 'transport': t[2], 'port': t[3], 'token': t[4], 'config': config, 'status': t[6]
            })
        return render_template('tunnels.html', tunnels=tunnels_list)
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return render_template('tunnels.html', tunnels=[])

@tunnels_bp.route('/edit-tunnel/<int:tunnel_id>', methods=['GET', 'POST'])
@login_required
def edit_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel:
        flash('Tunnel not found.', 'danger')
        return redirect(url_for('tunnels.list_tunnels'))

    try: current_config = json.loads(tunnel[5])
    except: current_config = {}

    if request.method == 'POST':
        flash('To edit core settings, please recreate the tunnel.', 'info')
        return redirect(url_for('tunnels.list_tunnels'))

    return render_template('edit_tunnel.html', tunnel=tunnel, config=current_config)

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
@login_required
def delete_tunnel(tunnel_id):
    try:
        tunnel = get_tunnel_by_id(tunnel_id)
        if tunnel:
            transport = tunnel[2]
            # توقف سرویس‌ها
            if "rathole" in transport: 
                svc = f"rathole-iran{tunnel[3]}"
                os.system(f"systemctl stop {svc} && systemctl disable {svc} && rm /etc/systemd/system/{svc}.service")
            elif "hysteria" in transport:
                os.system("systemctl stop hysteria-client && systemctl disable hysteria-client")
            elif "slipstream" in transport:
                os.system("systemctl stop slipstream-client && systemctl disable slipstream-client")
            else:
                stop_and_delete_backhaul()
            
            delete_tunnel_by_id(tunnel_id)
            os.system("systemctl daemon-reload")
            flash('Tunnel deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting tunnel: {str(e)}', 'danger')
        
    return redirect(url_for('tunnels.list_tunnels'))