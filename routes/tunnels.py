# AlamorTunnel/routes/tunnels.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
# ایمپورت توابع دیتابیس
from core.database import (get_connected_server, add_tunnel, get_all_tunnels, 
                           get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config)
# ایمپورت منیجرها
from core.backhaul_manager import (install_local_backhaul, install_remote_backhaul, 
                                   generate_token, stop_and_delete_backhaul)
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import (install_hysteria_server_remote, 
                                   install_hysteria_client_local, generate_pass)
# ایمپورت Slipstream (نسخه Generator برای لاگ زنده)
from core.slipstream_manager import (install_slipstream_server_remote_gen, 
                                     install_slipstream_client_local_gen)
# ایمپورت احراز هویت و تسک‌ها
from routes.auth import login_required
from core.tasks import task_queue, init_task

import json
import os
import subprocess
import uuid
import re

tunnels_bp = Blueprint('tunnels', __name__)

def get_server_public_ip():
    """تلاش برای پیدا کردن آی‌پی سرور ایران"""
    commands = ["curl -s --max-time 3 ifconfig.me", "curl -s --max-time 3 api.ipify.org"]
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if len(output) > 5 and len(output) < 20: return output
        except: continue
    return "YOUR_IRAN_IP"

# ==========================================
#  GENERATOR FUNCTIONS (Task Processors)
#  این توابع داخل Worker اجرا می‌شوند
# ==========================================

def process_hysteria(server_ip, config):
    yield 10, "Syncing Time & Installing Remote Server..."
    os.system("apt-get install -y ntpdate && ntpdate pool.ntp.org")
    
    success, msg = install_hysteria_server_remote(server_ip, config)
    if not success: raise Exception(f"Remote Install Failed: {msg}")
    
    yield 50, "Configuring Local Client..."
    install_hysteria_client_local(server_ip, config)
    
    yield 90, "Saving to Database..."
    add_tunnel(f"Hysteria2-{config['tunnel_port']}", "hysteria", config['tunnel_port'], config['password'], config)
    yield 100, "Installation Complete!"

def process_slipstream(server_ip, config):
    """
    نصب Slipstream با قابلیت نمایش لاگ زنده (Real-time Logs)
    """
    yield 5, "Initializing Remote Build Environment..."
    
    # --- Remote Install (Server) ---
    # چون تابع منیجر، لاگ‌ها را Yield می‌کند، ما هم اینجا آن‌ها را به کاربر پاس می‌دهیم
    step_count = 0
    for log in install_slipstream_server_remote_gen(server_ip, config):
        step_count += 1
        # محاسبه درصد تقریبی بر اساس تعداد لاگ‌ها یا محتوای آن‌ها
        progress = 10
        if "Updating submodules" in log: progress = 15
        elif "Compiling" in log: progress = 20 + (step_count % 25) # حرکت مصنوعی نوار
        elif "Finished release" in log: progress = 45
        elif "Server Service Started" in log: progress = 50
        
        # کوتاه کردن لاگ‌های خیلی طولانی
        clean_log = log[-60:] if len(log) > 60 else log
        yield progress, f"Remote: {clean_log}"
        
    yield 50, "Starting Local Client Build (Wait ~5 mins)..."
    
    # --- Local Install (Client) ---
    step_count = 0
    for log in install_slipstream_client_local_gen(server_ip, config):
        step_count += 1
        progress = 50
        if "Compiling" in log: progress = 55 + (step_count % 35)
        elif "Finished" in log: progress = 90
        elif "Local Service Started" in log: progress = 95
        
        clean_log = log[-60:] if len(log) > 60 else log
        yield progress, f"Local: {clean_log}"
    
    yield 98, "Finalizing Database..."
    add_tunnel(f"Slipstream-{config['tunnel_port']}", "slipstream", config['client_port'], "N/A", config)
    yield 100, "Slipstream Tunnel Ready!"

def process_rathole(server_ip, iran_ip, config):
    yield 10, "Configuring Remote Rathole..."
    success, msg = install_remote_rathole(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
    
    yield 60, "Configuring Local Rathole..."
    install_local_rathole(config)
    
    yield 90, "Saving Config..."
    add_tunnel(f"Rathole-{config['tunnel_port']}", "rathole", config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

def process_backhaul(server_ip, iran_ip, config):
    yield 10, "Setting up Remote Backhaul..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
    
    yield 60, "Setting up Local Backhaul..."
    install_local_backhaul(config)
    
    yield 90, "Saving Config..."
    add_tunnel("Backhaul Tunnel", config['transport'], config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

# ==========================================
#  INSTALL ROUTE (Async Handler)
# ==========================================

@tunnels_bp.route('/start-install/<protocol>', methods=['POST'])
@login_required
def start_install(protocol):
    server = get_connected_server()
    if not server:
        return jsonify({'status': 'error', 'message': 'No foreign server connected. Please connect via dashboard.'})

    # دریافت تمام داده‌های فرم
    form_data = request.form.to_dict()
    config = form_data.copy()
    
    # ایجاد تسک جدید
    task_id = str(uuid.uuid4())
    init_task(task_id) # ثبت وضعیت اولیه برای جلوگیری از Undefined

    # --- HYSTERIA CONFIG ---
    if protocol == 'hysteria':
        raw_ports = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
        if not config['ports']:
            return jsonify({'status': 'error', 'message': 'At least one forward port is required.'})
            
        config['password'] = config.get('password') or generate_pass()
        config['obfs_pass'] = config.get('obfs_pass') or generate_pass()
        
        task_queue.put((task_id, process_hysteria, (server[0], config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    # --- SLIPSTREAM CONFIG ---
    elif protocol == 'slipstream':
        # مقادیر پیش‌فرض
        if not config.get('domain'): config['domain'] = 'dl.google.com'
        if not config.get('dest_port'): config['dest_port'] = '8080' # پورت مقصد در خارج
        if not config.get('client_port'): config['client_port'] = '8443' # پورت کلاینت در ایران
        
        task_queue.put((task_id, process_slipstream, (server[0], config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    # --- RATHOLE CONFIG ---
    elif protocol == 'rathole':
        iran_ip = get_server_public_ip()
        raw_ports = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
        config['token'] = config.get('token') or generate_token()
        
        # تبدیل چک‌باکس‌ها
        config['ipv6'] = request.form.get('ipv6') == 'on'
        config['nodelay'] = request.form.get('nodelay') == 'on'
        config['heartbeat'] = request.form.get('heartbeat') == 'on'
        
        task_queue.put((task_id, process_rathole, (server[0], iran_ip, config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    # --- BACKHAUL CONFIG (ADVANCED) ---
    elif protocol == 'backhaul':
        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        config['token'] = generate_token()
        
        # پورت‌ها (چند خطی)
        config['port_rules'] = [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()]
        
        # تبدیل Boolean ها
        bool_fields = ['accept_udp', 'nodelay', 'sniffer', 'skip_optz', 'aggressive_pool']
        for field in bool_fields:
            config[field] = request.form.get(field) == 'on'
            
        # تبدیل اعداد (Integer) با ایمنی
        int_fields = [
            'keepalive_period', 'heartbeat', 'mux_con', 'channel_size', 'mss', 
            'so_rcvbuf', 'so_sndbuf', 'client_so_rcvbuf', 'client_so_sndbuf', 
            'connection_pool', 'retry_interval', 'dial_timeout', 'web_port', 
            'mux_version', 'mux_framesize', 'mux_recievebuffer', 'mux_streambuffer'
        ]
        for field in int_fields:
            if config.get(field):
                try: config[field] = int(config[field])
                except ValueError: pass # اگر عدد نبود، رشته می‌ماند یا نادیده گرفته می‌شود
            
        config['tls_cert'] = '/root/certs/server.crt'
        config['tls_key'] = '/root/certs/server.key'

        task_queue.put((task_id, process_backhaul, (server[0], iran_ip, config)))
        return jsonify({'status': 'started', 'task_id': task_id})

    return jsonify({'status': 'error', 'message': 'Unknown protocol selected'})

# ==========================================
#  STANDARD ROUTES (List, Edit, Delete)
# ==========================================

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
                'id': t[0], 
                'name': t[1], 
                'transport': t[2], 
                'port': t[3], 
                'token': t[4], 
                'config': config, 
                'status': t[6]
            })
        return render_template('tunnels.html', tunnels=tunnels_list)
    except Exception as e:
        flash(f'Error listing tunnels: {str(e)}', 'danger')
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
        # به دلیل پیچیدگی هماهنگی سرور لوکال و ریموت، پیشنهاد می‌شود تانل دوباره ساخته شود
        flash('For stability, please delete and recreate the tunnel to change core settings.', 'info')
        return redirect(url_for('tunnels.list_tunnels'))

    return render_template('edit_tunnel.html', tunnel=tunnel, config=current_config)

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
@login_required
def delete_tunnel(tunnel_id):
    try:
        tunnel = get_tunnel_by_id(tunnel_id)
        if tunnel:
            transport = tunnel[2]
            # توقف سرویس‌ها بر اساس نوع تانل
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
            flash('Tunnel deleted and services stopped.', 'success')
    except Exception as e:
        flash(f'Error deleting tunnel: {str(e)}', 'danger')
        
    return redirect(url_for('tunnels.list_tunnels'))