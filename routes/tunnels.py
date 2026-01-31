from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from core.database import get_connected_server, add_tunnel, get_all_tunnels, get_tunnel_by_id, delete_tunnel_by_id, update_tunnel_config
from core.backhaul_manager import install_local_backhaul, install_remote_backhaul, generate_token, stop_and_delete_backhaul
from core.rathole_manager import install_local_rathole, install_remote_rathole
from core.hysteria_manager import install_hysteria_server_remote, install_hysteria_client_local, generate_pass
from core.slipstream_manager import install_slipstream_server_remote, install_slipstream_client_local
import json
import os
import re
import subprocess

tunnels_bp = Blueprint('tunnels', __name__)

def is_logged_in(): return 'user' in session

@tunnels_bp.route('/tunnels')
def list_tunnels():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    
    raw_tunnels = get_all_tunnels()
    tunnels_list = []
    
    for t in raw_tunnels:
        try: config = json.loads(t[5])
        except: config = {}
        tunnels_list.append({
            'id': t[0], 'name': t[1], 'transport': t[2], 'port': t[3], 'token': t[4], 'config': config, 'status': t[6]
        })
    return render_template('tunnels.html', tunnels=tunnels_list)

@tunnels_bp.route('/install-hysteria', methods=['POST'])
def install_hysteria():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    server = get_connected_server()
    if not server: return redirect(url_for('dashboard.index'))

    raw_ports = request.form.get('forward_ports', '')
    ports_list = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]
    
    if not ports_list:
        flash('Valid ports required.', 'warning')
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
        flash(f'Remote Hysteria Failed: {msg_remote}', 'danger')
        return redirect(url_for('dashboard.index'))

    try:
        install_hysteria_client_local(server[0], config_data)
        add_tunnel(f"Hysteria2-{config_data['tunnel_port']}", "hysteria", config_data['tunnel_port'], config_data['password'], config_data)
        flash(f'Hysteria 2 Tunnel Established!', 'success')
        return redirect(url_for('tunnels.list_tunnels'))
    except Exception as e:
        flash(f'Local Hysteria Failed: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@tunnels_bp.route('/install-slipstream', methods=['POST'])
def install_slipstream():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    server = get_connected_server()
    if not server: return redirect(url_for('dashboard.index'))
    
    config_data = {
        'tunnel_port': request.form.get('tunnel_port', '8853'),
        'client_port': request.form.get('client_port', '8443'),
        'dest_port': request.form.get('dest_port', '8443'),
        'domain': request.form.get('domain', 'google.com')
    }

    flash('Building Slipstream (Rust)... Please wait 5-10 mins.', 'info')
    
    try:
        success_remote, msg_remote = install_slipstream_server_remote(server[0], config_data)
        if not success_remote:
            flash(f'Remote Error: {msg_remote}', 'danger')
            return redirect(url_for('dashboard.index'))
            
        install_slipstream_client_local(server[0], config_data)
        add_tunnel(f"Slipstream-{config_data['tunnel_port']}", "slipstream", config_data['client_port'], "N/A", config_data)
        flash('Slipstream Tunnel Installed!', 'success')
        return redirect(url_for('tunnels.list_tunnels'))
    except Exception as e:
        flash(f'Local Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard.index'))

@tunnels_bp.route('/install-rathole', methods=['POST'])
def install_rathole():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    server = get_connected_server()
    if not server: return redirect(url_for('dashboard.index'))

    iran_ip = request.form.get('iran_ip_manual') or "YOUR_IP"
    raw_ports = request.form.get('forward_ports', '')
    ports_list = [p.strip() for p in raw_ports.split(',') if p.strip().isdigit()]

    config_data = {
        'tunnel_port': request.form.get('tunnel_port'),
        'transport': request.form.get('transport'),
        'token': generate_token(),
        'ipv6': False, 'nodelay': True, 'heartbeat': True,
        'ports': ports_list
    }

    success_remote, msg_remote = install_remote_rathole(server[0], iran_ip, config_data)
    if not success_remote:
        flash(f'Remote Error: {msg_remote}', 'danger')
        return redirect(url_for('dashboard.index'))

    install_local_rathole(config_data)
    add_tunnel(f"Rathole-{config_data['tunnel_port']}", "rathole", config_data['tunnel_port'], config_data['token'], config_data)
    flash('Rathole Installed!', 'success')
    return redirect(url_for('tunnels.list_tunnels'))

@tunnels_bp.route('/install-backhaul', methods=['POST'])
def install_backhaul():
    if not is_logged_in(): return redirect(url_for('auth.login'))
    server = get_connected_server()
    if not server: return redirect(url_for('dashboard.index'))

    iran_ip = request.form.get('iran_ip_manual') or "YOUR_IP"
    config_data = {
        'transport': request.form.get('transport'),
        'tunnel_port': request.form.get('tunnel_port'),
        'token': generate_token(),
        'nodelay': True, 'sniffer': False,
        'port_rules': []
    }

    success_remote, msg_remote = install_remote_backhaul(server[0], iran_ip, config_data)
    if not success_remote:
        flash(f'Remote Error: {msg_remote}', 'danger')
        return redirect(url_for('dashboard.index'))

    install_local_backhaul(config_data)
    add_tunnel("Backhaul Tunnel", config_data['transport'], config_data['tunnel_port'], config_data['token'], config_data)
    flash('Backhaul Installed!', 'success')
    return redirect(url_for('tunnels.list_tunnels'))

@tunnels_bp.route('/delete-tunnel/<int:tunnel_id>')
def delete_tunnel(tunnel_id):
    if not is_logged_in(): return redirect(url_for('auth.login'))
    tunnel = get_tunnel_by_id(tunnel_id)
    if tunnel:
        transport = tunnel[2]
        if "hysteria" in transport:
            os.system("systemctl stop hysteria-client && systemctl disable hysteria-client")
        elif "slipstream" in transport:
            os.system("systemctl stop slipstream-client && systemctl disable slipstream-client")
        elif "rathole" in transport:
             svc = f"rathole-iran{tunnel[3]}"
             os.system(f"systemctl stop {svc} && systemctl disable {svc} && rm /etc/systemd/system/{svc}.service")
        else:
            stop_and_delete_backhaul()
            
        delete_tunnel_by_id(tunnel_id)
        flash('Tunnel Deleted.', 'success')
    return redirect(url_for('tunnels.list_tunnels'))

@tunnels_bp.route('/edit-tunnel/<int:tunnel_id>', methods=['GET', 'POST'])
def edit_tunnel(tunnel_id):
    if not is_logged_in(): return redirect(url_for('auth.login'))
    tunnel = get_tunnel_by_id(tunnel_id)
    try: config = json.loads(tunnel[5])
    except: config = {}
    
    if request.method == 'POST':
        # فعلا فقط ریدایرکت میکنیم تا کد پیچیده نشود، ادیت باید مثل اینستال باشد
        flash('Please delete and reinstall tunnel to edit (Simpler for now).', 'info')
        return redirect(url_for('tunnels.list_tunnels'))

    return render_template('edit_tunnel.html', tunnel=tunnel, config=config)