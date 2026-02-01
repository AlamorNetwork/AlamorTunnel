from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import install_hysteria_server_remote, install_hysteria_client_local, generate_pass
from core.slipstream_manager import install_slipstream_server_remote_gen, install_slipstream_client_local_gen
from core.gost_manager import install_gost_server_remote, install_gost_client_local
from core.traffic import get_traffic_stats, check_port_health, run_speedtest
from core.tasks import task_queue, init_task
from routes.auth import login_required
import uuid
import os
import subprocess
import json
import re

tunnels_bp = Blueprint('tunnels', __name__)

def get_server_public_ip():
    """دریافت آی‌پی سرور با دقت بالا و حذف خروجی‌های HTML"""
    providers = [
        "curl -s --max-time 3 https://api.ipify.org",
        "curl -s --max-time 3 https://icanhazip.com",
        "curl -s --max-time 3 http://ifconfig.me/ip"
    ]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    
    for cmd in providers:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output):
                return output
        except:
            continue
    return "127.0.0.1"  # اگر پیدا نشد، پیش‌فرض امن

# --- GENERATORS ---
def process_gost(server_ip, config):
    yield 20, "Remote Install..."
    success, msg = install_gost_server_remote(server_ip, config)
    if not success: raise Exception(f"Remote Failed: {msg}")
    yield 60, "Local Config..."
    install_gost_client_local(server_ip, config)
    yield 90, "Saving..."
    add_tunnel(f"GOST-{config['tunnel_port']}", "gost", config['client_port'], "N/A", config)
    yield 100, "Done!"

def process_slipstream(server_ip, config):
    yield 5, "Remote Init..."
    for log in install_slipstream_server_remote_gen(server_ip, config):
        yield 20, f"Remote: {log[-40:]}"
    yield 50, "Local Build..."
    for log in install_slipstream_client_local_gen(server_ip, config):
        yield 70, f"Local: {log[-40:]}"
    yield 95, "Saving..."
    add_tunnel(f"Slipstream-{config['tunnel_port']}", "slipstream", config['client_port'], "N/A", config)
    yield 100, "Done!"

def process_hysteria(server_ip, config):
    yield 10, "Remote Install..."
    os.system("apt-get install -y ntpdate && ntpdate pool.ntp.org")
    success, msg = install_hysteria_server_remote(server_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Local Config..."
    install_hysteria_client_local(server_ip, config)
    yield 90, "Saving..."
    add_tunnel(f"Hysteria2-{config['tunnel_port']}", "hysteria", config['tunnel_port'], config['password'], config)
    yield 100, "Done!"

def process_rathole(server_ip, iran_ip, config):
    yield 10, "Remote Install..."
    success, msg = install_remote_rathole(server_ip, iran_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Local Config..."
    install_local_rathole(config)
    yield 90, "Saving..."
    add_tunnel(f"Rathole-{config['tunnel_port']}", "rathole", config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

def process_backhaul(server_ip, iran_ip, config):
    yield 10, "Remote Setup..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(msg)
    yield 60, "Local Setup..."
    install_local_backhaul(config)
    yield 90, "Saving..."
    add_tunnel("Backhaul Tunnel", config['transport'], config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

# --- ROUTES ---
@tunnels_bp.route('/start-install/<protocol>', methods=['POST'])
@login_required
def start_install(protocol):
    server = get_connected_server()
    if not server: return jsonify({'status': 'error', 'message': 'No server connected'})
    
    config = request.form.to_dict()
    task_id = str(uuid.uuid4())
    init_task(task_id)

    if protocol == 'gost':
        task_queue.put((task_id, process_gost, (server[0], config)))
        
    elif protocol == 'slipstream':
        if not config.get('domain'): config['domain'] = 'dl.google.com'
        if not config.get('dest_port'): config['dest_port'] = '8080'
        if not config.get('client_port'): config['client_port'] = '8443'
        task_queue.put((task_id, process_slipstream, (server[0], config)))
        
    elif protocol == 'hysteria':
        raw = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw.split(',') if p.strip().isdigit()]
        config['password'] = config.get('password') or generate_pass()
        config['obfs_pass'] = config.get('obfs_pass') or generate_pass()
        task_queue.put((task_id, process_hysteria, (server[0], config)))
        
    elif protocol == 'rathole':
        iran_ip = get_server_public_ip()
        raw = config.get('forward_ports', '')
        config['ports'] = [p.strip() for p in raw.split(',') if p.strip().isdigit()]
        config['token'] = config.get('token') or generate_token()
        config['ipv6'] = request.form.get('ipv6') == 'on'
        config['nodelay'] = request.form.get('nodelay') == 'on'
        config['heartbeat'] = request.form.get('heartbeat') == 'on'
        task_queue.put((task_id, process_rathole, (server[0], iran_ip, config)))
        
    elif protocol == 'backhaul':
        # اصلاح: دریافت IP واقعی به جای HTML خطا
        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        
        config['token'] = generate_token()
        
        # پردازش پورت‌ها
        raw_ports = request.form.get('port_rules', '').strip()
        config['port_rules'] = [l.strip() for l in raw_ports.split('\n') if l.strip()]
        
        # فیلدهای بولین
        bool_fields = ['accept_udp', 'nodelay', 'sniffer', 'skip_optz', 'aggressive_pool']
        for f in bool_fields:
            config[f] = request.form.get(f) == 'on'
            
        # فیلدهای عددی
        int_fields = [
            'keepalive_period', 'heartbeat', 'mux_con', 'channel_size', 'mss', 
            'so_rcvbuf', 'so_sndbuf', 'mux_version', 'mux_framesize', 
            'mux_recievebuffer', 'mux_streambuffer', 'web_port', 
            'dial_timeout', 'retry_interval', 'connection_pool', 'tunnel_port'
        ]
        for f in int_fields:
            val = request.form.get(f)
            if val and val.isdigit():
                config[f] = int(val)
        
        # مسیر سرتیفیکیت
        config['tls_cert'] = '/root/certs/server.crt'
        config['tls_key'] = '/root/certs/server.key'
        
        task_queue.put((task_id, process_backhaul, (server[0], iran_ip, config)))
    
    return jsonify({'status': 'started', 'task_id': task_id})

@tunnels_bp.route('/tunnel/stats/<int:tunnel_id>')
@login_required
def tunnel_stats(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel: return jsonify({'error': 'Not found'})
    
    try:
        # مدیریت انواع داده برای جلوگیری از کرش
        port_val = tunnel['port'] if tunnel['port'] else "0"
        port = int(port_val)
    except:
        port = 0
        
    transport = tunnel['transport']
    proto = 'udp' if 'hysteria' in transport or 'slipstream' in transport else 'tcp'
    
    rx, tx = get_traffic_stats(port, proto)
    health = check_port_health(port, proto)
    return jsonify({'rx_bytes': rx, 'tx_bytes': tx, 'status': health['status'], 'latency': health['latency']})

@tunnels_bp.route('/server/speedtest')
@login_required
def server_speedtest_route():
    return jsonify(run_speedtest())

@tunnels_bp.route('/tunnels')
@login_required
def list_tunnels():
    tunnels = get_all_tunnels()
    return render_template('tunnels.html', tunnels=tunnels)

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

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
@login_required
def delete_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if tunnel:
        transport = tunnel['transport']
        port = tunnel['port']
        
        if "gost" in transport: os.system("systemctl stop gost-client")
        elif "slipstream" in transport: os.system("systemctl stop slipstream-client")
        elif "hysteria" in transport: os.system("systemctl stop hysteria-client")
        elif "rathole" in transport: 
            svc = f"rathole-iran{port}"
            os.system(f"systemctl stop {svc} && systemctl disable {svc} && rm /etc/systemd/system/{svc}.service")
        elif "backhaul" in transport: # حذف مخصوص بکهال
             stop_and_delete_backhaul()
             
    delete_tunnel_by_id(tunnel_id)
    os.system("systemctl daemon-reload")
    flash('Tunnel deleted.', 'warning')
    return redirect(url_for('tunnels.list_tunnels'))