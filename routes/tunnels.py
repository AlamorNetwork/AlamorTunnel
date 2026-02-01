from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from core.database import get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id
# ایمپورت منیجرها
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import install_hysteria_server_remote, install_hysteria_client_local, generate_pass
from core.slipstream_manager import install_slipstream_server_remote_gen, install_slipstream_client_local_gen
from core.gost_manager import install_gost_server_remote, install_gost_client_local
# ایمپورت مانیتورینگ و تسک
from core.traffic import get_traffic_stats, check_port_health, run_speedtest
from core.tasks import task_queue, init_task
from routes.auth import login_required
import uuid
import os
import subprocess

tunnels_bp = Blueprint('tunnels', __name__)

def get_server_public_ip():
    try: return subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    except: return "1.1.1.1"

# --- GENERATORS (توابع نصب با گزارش وضعیت) ---

def process_gost(server_ip, config):
    yield 20, "Installing Remote GOST..."
    success, msg = install_gost_server_remote(server_ip, config)
    if not success: raise Exception(f"Remote Failed: {msg}")
    
    yield 60, "Configuring Local Client..."
    install_gost_client_local(server_ip, config)
    
    yield 90, "Saving Configuration..."
    add_tunnel(f"GOST-{config['tunnel_port']}", "gost", config['client_port'], "N/A", config)
    yield 100, "Done!"

def process_slipstream(server_ip, config):
    yield 5, "Remote: Initializing..."
    # استفاده از لاگ زنده Slipstream
    for log in install_slipstream_server_remote_gen(server_ip, config):
        yield 20, f"Remote: {log[-50:]}" # نمایش 50 کاراکتر آخر لاگ
        
    yield 50, "Local: Building Client (This takes time)..."
    for log in install_slipstream_client_local_gen(server_ip, config):
        yield 70, f"Local: {log[-50:]}"
        
    yield 95, "Saving..."
    add_tunnel(f"Slipstream-{config['tunnel_port']}", "slipstream", config['client_port'], "N/A", config)
    yield 100, "Done!"

def process_hysteria(server_ip, config):
    yield 10, "Installing Remote Server..."
    os.system("apt-get install -y ntpdate && ntpdate pool.ntp.org")
    success, msg = install_hysteria_server_remote(server_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
    
    yield 60, "Configuring Local Client..."
    install_hysteria_client_local(server_ip, config)
    yield 90, "Saving..."
    add_tunnel(f"Hysteria2-{config['tunnel_port']}", "hysteria", config['tunnel_port'], config['password'], config)
    yield 100, "Done!"

def process_rathole(server_ip, iran_ip, config):
    yield 10, "Configuring Remote Rathole..."
    success, msg = install_remote_rathole(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
    yield 60, "Local Config..."
    install_local_rathole(config)
    yield 90, "Saving..."
    add_tunnel(f"Rathole-{config['tunnel_port']}", "rathole", config['tunnel_port'], config['token'], config)
    yield 100, "Done!"

def process_backhaul(server_ip, iran_ip, config):
    yield 10, "Remote Setup..."
    success, msg = install_remote_backhaul(server_ip, iran_ip, config)
    if not success: raise Exception(f"Remote Error: {msg}")
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

    # Dispatch tasks based on protocol
    if protocol == 'gost':
        task_queue.put((task_id, process_gost, (server[0], config)))
        
    elif protocol == 'slipstream':
        if not config.get('domain'): config['domain'] = 'dl.google.com'
        if not config.get('dest_port'): config['dest_port'] = '8080'
        if not config.get('client_port'): config['client_port'] = '8443'
        task_queue.put((task_id, process_slipstream, (server[0], config)))
        
    elif protocol == 'hysteria':
        # پورت‌ها و پسوردها
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
        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        config['token'] = generate_token()
        config['port_rules'] = [l.strip() for l in request.form.get('port_rules', '').split('\n') if l.strip()]
        
        # هندل کردن چک‌باکس‌ها
        for f in ['accept_udp', 'nodelay', 'sniffer', 'skip_optz', 'aggressive_pool']:
            config[f] = request.form.get(f) == 'on'
        
        # تبدیل اعداد
        for f in ['keepalive_period', 'heartbeat', 'mux_con', 'channel_size', 'mss', 'so_rcvbuf', 'so_sndbuf']:
            if config.get(f): 
                try: config[f] = int(config[f])
                except: pass
                
        config['tls_cert'] = '/root/certs/server.crt'
        config['tls_key'] = '/root/certs/server.key'
        task_queue.put((task_id, process_backhaul, (server[0], iran_ip, config)))
    
    return jsonify({'status': 'started', 'task_id': task_id})

# --- Monitoring Routes ---
@tunnels_bp.route('/tunnel/stats/<int:tunnel_id>')
@login_required
def tunnel_stats(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if not tunnel: return jsonify({'error': 'Not found'})
    
    port = int(tunnel[3]) if tunnel[3].isdigit() else 0
    proto = 'udp' if 'hysteria' in tunnel[2] or 'slipstream' in tunnel[2] else 'tcp'
    
    rx, tx = get_traffic_stats(port, proto)
    health = check_port_health(port, proto)
    
    return jsonify({'rx_bytes': rx, 'tx_bytes': tx, 'status': health['status'], 'latency': health['latency']})

@tunnels_bp.route('/server/speedtest')
@login_required
def server_speedtest():
    return jsonify(run_speedtest())

# --- Basic Routes ---
@tunnels_bp.route('/tunnels')
@login_required
def list_tunnels():
    tunnels = get_all_tunnels()
    return render_template('tunnels.html', tunnels=tunnels)

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
@login_required
def delete_tunnel(tunnel_id):
    tunnel = get_tunnel_by_id(tunnel_id)
    if tunnel:
        if "gost" in tunnel[2]: os.system("systemctl stop gost-client")
        elif "slipstream" in tunnel[2]: os.system("systemctl stop slipstream-client")
        elif "hysteria" in tunnel[2]: os.system("systemctl stop hysteria-client")
        elif "rathole" in tunnel[2]: 
            svc = f"rathole-iran{tunnel[3]}"
            os.system(f"systemctl stop {svc} && systemctl disable {svc} && rm /etc/systemd/system/{svc}.service")
        else: stop_and_delete_backhaul()
            
    delete_tunnel_by_id(tunnel_id)
    os.system("systemctl daemon-reload")
    return redirect(url_for('tunnels.list_tunnels'))