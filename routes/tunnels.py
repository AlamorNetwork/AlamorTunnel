from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from core.database import (get_connected_server, add_tunnel, get_all_tunnels, 
                           get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config)
from core.backhaul_manager import (install_local_backhaul, install_remote_backhaul, 
                                   generate_token, stop_and_delete_backhaul)
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import (install_hysteria_server_remote, 
                                   install_hysteria_client_local, generate_pass)
from core.slipstream_manager import (install_slipstream_server_remote, 
                                     install_slipstream_client_local)
from routes.auth import login_required
import json
import os
import subprocess
import re

tunnels_bp = Blueprint('tunnels', __name__)

def get_server_public_ip():
    commands = [
        "curl -s --max-time 3 ifconfig.me", 
        "curl -s --max-time 3 api.ipify.org",
        "hostname -I | awk '{print $1}'"
    ]
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    for cmd in commands:
        try:
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if ip_pattern.match(output): return output
        except: continue
    return "YOUR_IRAN_IP"

# --- LIST TUNNELS ---
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
        flash(f'Error fetching tunnels: {str(e)}', 'danger')
        return render_template('tunnels.html', tunnels=[])

# --- INSTALL ROUTES ---
@tunnels_bp.route('/install-hysteria', methods=['POST'])
@login_required
def install_hysteria():
    try:
        server = get_connected_server()
        if not server:
            flash('Foreign server not connected.', 'warning')
            return redirect(url_for('dashboard.index'))

        raw_ports = request.form.get('forward_ports', '')
        ports_list = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
        
        if not ports_list:
            flash('At least one valid port is required.', 'warning')
            return redirect(url_for('dashboard.index'))

        config_data = {
            'tunnel_port': request.form.get('tunnel_port'), 
            'password': request.form.get('password') or generate_pass(),
            'obfs_pass': request.form.get('obfs_pass') or generate_pass(),
            'up_mbps': request.form.get('up_mbps', '100'),
            'down_mbps': request.form.get('down_mbps', '100'),
            'ports': ports_list
        }
        
        os.system("apt-get install -y ntpdate && ntpdate pool.ntp.org")
        success_remote, msg_remote = install_hysteria_server_remote(server[0], config_data)
        if not success_remote:
            flash(f'Remote Installation Failed: {msg_remote}', 'danger')
            return redirect(url_for('dashboard.index'))

        install_hysteria_client_local(server[0], config_data)
        add_tunnel(f"Hysteria2-{config_data['tunnel_port']}", "hysteria", 
                   config_data['tunnel_port'], config_data['password'], config_data)
        flash(f'Hysteria 2 Tunnel successfully created.', 'success')
    except Exception as e:
        flash(f'Critical Error: {str(e)}', 'danger')
    return redirect(url_for('tunnels.list_tunnels'))

@tunnels_bp.route('/install-slipstream', methods=['POST'])
@login_required
def install_slipstream():
    try:
        server = get_connected_server()
        if not server:
            flash('Foreign server not connected.', 'warning')
            return redirect(url_for('dashboard.index'))
        
        config_data = {
            'tunnel_port': request.form.get('tunnel_port', '8853'),
            'client_port': request.form.get('client_port', '8443'),
            'dest_port': request.form.get('dest_port', '8443'),
            'domain': request.form.get('domain', 'google.com')
        }

        flash('Building Slipstream (Rust)... This may take 5-10 minutes.', 'info')
        success_remote, msg_remote = install_slipstream_server_remote(server[0], config_data)
        if not success_remote:
            flash(f'Remote Build Failed: {msg_remote}', 'danger')
            return redirect(url_for('dashboard.index'))

        install_slipstream_client_local(server[0], config_data)
        add_tunnel(f"Slipstream-{config_data['tunnel_port']}", "slipstream", 
                   config_data['client_port'], "N/A", config_data)
        flash('Slipstream Tunnel Installed!', 'success')
    except Exception as e:
        flash(f'Installation Error: {str(e)}', 'danger')
    return redirect(url_for('tunnels.list_tunnels'))

@tunnels_bp.route('/install-rathole', methods=['POST'])
@login_required
def install_rathole():
    try:
        server = get_connected_server()
        if not server:
            flash('Foreign server not connected.', 'warning')
            return redirect(url_for('dashboard.index'))

        iran_ip = request.form.get('iran_ip_manual') or get_server_public_ip()
        raw_ports = request.form.get('forward_ports', '')
        ports_list = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]

        if not ports_list:
            flash('Please specify ports to forward.', 'warning')
            return redirect(url_for('dashboard.index'))

        config_data = {
            'tunnel_port': request.form.get('tunnel_port'),
            'transport': request.form.get('transport', 'tcp'),
            'token': request.form.get('token') or generate_token(),
            'ipv6': request.form.get('ipv6') == 'on',
            'nodelay': request.form.get('nodelay') == 'on',
            'heartbeat': request.form.get('heartbeat') == 'on',
            'ports': ports_list
        }

        success_remote, msg_remote = install_remote_rathole(server[0], iran_ip, config_data)
        if not success_remote:
            flash(f'Remote Error: {msg_remote}', 'danger')
            return redirect(url_for('dashboard.index'))

        install_local_rathole(config_data)
        add_tunnel(f"Rathole-{config_data['tunnel_port']}", "rathole", 
                   config_data['tunnel_port'], config_data['token'], config_data)
        flash('Rathole Tunnel Created!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('tunnels.list_tunnels'))

@tunnels_bp.route('/install-backhaul', methods=['POST'])
@login_required
def install_backhaul():
    try:
        from core.database import get_connected_server, add_tunnel
        server = get_connected_server()
        if not server:
            flash('Foreign server not connected.', 'warning')
            return redirect(url_for('dashboard.index'))

        iran_ip = request.form.get('iran_ip_manual') or "YOUR_IRAN_IP" # بهتر است از IP واقعی استفاده شود

        # دریافت تمام پارامترها از فرم
        config_data = {
            'transport': request.form.get('transport', 'tcp'),
            'tunnel_port': request.form.get('tunnel_port'),
            'token': generate_token(),
            'edge_ip': request.form.get('edge_ip'),
            'port_rules': [line.strip() for line in request.form.get('port_rules', '').split('\n') if line.strip()],
            
            # Boolean Flags
            'accept_udp': request.form.get('accept_udp') == 'on',
            'nodelay': request.form.get('nodelay') == 'on',
            'sniffer': request.form.get('sniffer') == 'on',
            'skip_optz': request.form.get('skip_optz') == 'on',
            'aggressive_pool': request.form.get('aggressive_pool') == 'on',

            # Advanced Integers / Strings
            'keepalive_period': int(request.form.get('keepalive_period', 75)),
            'heartbeat': int(request.form.get('heartbeat', 40)),
            'channel_size': int(request.form.get('channel_size', 2048)),
            'mux_con': int(request.form.get('mux_con', 8)),
            'mux_version': int(request.form.get('mux_version', 1)),
            'mux_framesize': int(request.form.get('mux_framesize', 32768)),
            'mux_recievebuffer': int(request.form.get('mux_recievebuffer', 4194304)),
            'mux_streambuffer': int(request.form.get('mux_streambuffer', 65536)),
            'connection_pool': int(request.form.get('connection_pool', 8)),
            'retry_interval': int(request.form.get('retry_interval', 3)),
            'dial_timeout': int(request.form.get('dial_timeout', 10)),
            'mss': int(request.form.get('mss', 1360)),
            'web_port': int(request.form.get('web_port', 2060)),
            'sniffer_log': request.form.get('sniffer_log', '/root/log.json'),
            'log_level': request.form.get('log_level', 'info'),

            # Buffers (Server)
            'so_rcvbuf': int(request.form.get('so_rcvbuf', 4194304)),
            'so_sndbuf': int(request.form.get('so_sndbuf', 1048576)),

            # Buffers (Client)
            'client_so_rcvbuf': int(request.form.get('client_so_rcvbuf', 1048576)),
            'client_so_sndbuf': int(request.form.get('client_so_sndbuf', 4194304)),

            # Paths
            'tls_cert': '/root/certs/server.crt',
            'tls_key': '/root/certs/server.key'
        }
        
        success_remote, msg_remote = install_remote_backhaul(server[0], iran_ip, config_data)
        if not success_remote:
            flash(f'Remote Error: {msg_remote}', 'danger')
            return redirect(url_for('dashboard.index'))

        install_local_backhaul(config_data)
        add_tunnel("Backhaul Tunnel", config_data['transport'], 
                   config_data['tunnel_port'], config_data['token'], config_data)
        
        flash('Backhaul Tunnel Configured with Advanced Settings.', 'success')

    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('tunnels.list_tunnels'))
@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
@login_required
def delete_tunnel(tunnel_id):
    try:
        tunnel = get_tunnel_by_id(tunnel_id)
        if tunnel:
            transport = tunnel[2]
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
            flash('Tunnel deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting tunnel: {str(e)}', 'danger')
    return redirect(url_for('tunnels.list_tunnels'))

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
        flash('Edit functionality requires full reinstall. Please delete and recreate.', 'info')
        return redirect(url_for('tunnels.list_tunnels'))
    return render_template('edit_tunnel.html', tunnel=tunnel, config=current_config)