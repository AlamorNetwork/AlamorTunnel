from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import install_hysteria_server_remote, install_hysteria_client_local, generate_pass
from core.slipstream_manager import install_slipstream_server_remote_gen, install_slipstream_client_local_gen
from core.gost_manager import install_gost_server_remote, install_gost_client_local
from core.traffic import get_traffic_stats, check_port_health, run_speedtest
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

# --- API وضعیت تسک (برای پروگرس بار) ---
@tunnels_bp.route('/api/task_status/<task_id>')
@login_required
def get_task_status(task_id):
    status = task_status.get(task_id, {'progress': 0, 'status': 'queued', 'log': 'Waiting...'})
    return jsonify(status)




def process_backhaul(server_ip, iran_ip, config):
    yield 10, f"Connecting to Remote Server..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(msg)
    
    yield 50, "Remote Done. Installing Local..."
    install_local_backhaul(config)
    
    # === تنظیم تانل روی Root (443) ===
    if config['transport'] in ['ws', 'wss', 'wsmux', 'wssmux']:
        yield 70, "Binding Tunnel to Domain Root (443)..."
        ok, nginx_msg = set_root_tunnel(config['tunnel_port'])
        if ok:
            config['ws_path'] = "/"
            config['domain_url'] = f"https://{load_config().get('panel_domain')}"
        else:
            yield 75, f"Warning: Nginx Error ({nginx_msg})"
    # =================================
    
    yield 90, "Saving..."
    add_tunnel("Backhaul Tunnel", config['transport'], config['tunnel_port'], config['token'], config)
    yield 100, "Done!"
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

# --- GENERATORS (مراحل نصب) ---
def process_backhaul(server_ip, iran_ip, config):
    yield 10, f"Connecting to Remote Server ({server_ip})..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Install Failed: {msg}")
    
    yield 50, "Remote Configured. Installing Local..."
    try:
        install_local_backhaul(config)
    except Exception as e: raise Exception(f"Local Install Failed: {e}")
        
    yield 80, "Local Configured. Saving to DB..."
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
@tunnels_bp.route('/stats/<int:id>')
def get_tunnel_stats(id):
    try:
        # دریافت آمار واقعی سرور
        net = psutil.net_io_counters()
        cpu = psutil.cpu_percent(interval=None)
        
        return jsonify({
            'status': 'online',
            'cpu': cpu,
            'ram': psutil.virtual_memory().percent,
            # تبدیل بایت به مگابایت
            'tx': round(net.bytes_sent / 1024 / 1024, 2),
            'rx': round(net.bytes_recv / 1024 / 1024, 2)
        })
    except:
        return jsonify({'status': 'offline', 'cpu': 0, 'tx': 0, 'rx': 0})
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
        
        # دریافت پسوردها (اگر خالی بود، تولید کن)
        config['password'] = config.get('password') or generate_pass()
        config['obfs_pass'] = config.get('obfs_pass') or generate_pass()
        
        # دریافت تنظیمات پیشرفته از فرم
        # اگر کاربر چیزی وارد نکرد، مقادیر پیش‌فرض را ست می‌کنیم
        config['hop_start'] = config.get('hop_start', '20000')
        config['hop_end'] = config.get('hop_end', '50000')
        config['hop_interval'] = config.get('hop_interval', '30s')
        config['up_mbps'] = config.get('up_mbps', '1000')
        config['down_mbps'] = config.get('down_mbps', '1000')
        config['masq_url'] = config.get('masq_url', 'https://www.bing.com')
        
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

@tunnels_bp.route('/server/speedtest')
@login_required
def server_speedtest():
    return jsonify(run_speedtest())

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
    proto = 'udp' if 'hysteria' in transport or 'slipstream' in transport else 'tcp'
    rx, tx = get_traffic_stats(port, proto)
    health = check_port_health(port, proto)
    return jsonify({'rx_bytes': rx, 'tx_bytes': tx, 'status': health['status'], 'latency': health['latency']})

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
@login_required
def delete_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if tunnel:
        transport = tunnel['transport']
        if "backhaul" in transport: stop_and_delete_backhaul()
    delete_tunnel_by_id(tunnel_id)
    os.system("systemctl daemon-reload")
    flash('Tunnel deleted.', 'warning')
    return redirect(url_for('tunnels.list_tunnels'))

# --- روت ویرایش (که باعث خطا شده بود) ---
@tunnels_bp.route('/edit/<int:tunnel_id>')
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

# --- روت آپدیت (POST) ---
@tunnels_bp.route('/tunnel/update/<int:tunnel_id>', methods=['POST'])
@login_required
def update_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel:
        flash('Tunnel not found!', 'danger')
        return redirect(url_for('tunnels.list_tunnels'))

    config = request.form.to_dict()
    # اینجا می‌توانید لاجیک آپدیت کانفیگ و ریستارت سرویس را اضافه کنید
    # فعلاً فقط دیتابیس را آپدیت می‌کنیم
    
    try:
        current_config = json.loads(tunnel['config'])
        current_config.update(config) # آپدیت مقادیر جدید
        update_tunnel_config(tunnel_id, tunnel['name'], tunnel['transport'], tunnel['port'], current_config)
        flash('Tunnel configuration updated (Service restart required).', 'success')
    except Exception as e:
        flash(f'Update failed: {str(e)}', 'danger')
        
    return redirect(url_for('tunnels.list_tunnels'))