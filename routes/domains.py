from flask import Blueprint, render_template, request, jsonify
from core.ssl_manager import check_domain_dns, generate_letsencrypt_cert, setup_secure_panel_nginx
from core.scanner import scan_for_clean_ip
from routes.auth import login_required
import secrets
import threading
import time
import os

domains_bp = Blueprint('domains', __name__)

@domains_bp.route('/domains')
@login_required
def index():
    return render_template('domains.html')

@domains_bp.route('/domains/check-dns', methods=['POST'])
@login_required
def check_dns():
    domain = request.form.get('domain')
    time.sleep(1)
    is_valid, message = check_domain_dns(domain)
    if is_valid: return jsonify({'status': 'ok', 'message': 'Domain verified.'})
    else: return jsonify({'status': 'error', 'message': message})

@domains_bp.route('/domains/scan-ips', methods=['POST'])
@login_required
def scan_ips():
    domain = request.form.get('domain')
    ips, logs = scan_for_clean_ip(domain)
    return jsonify({'status': 'ok', 'ips': ips, 'logs': logs})

@domains_bp.route('/domains/secure-panel', methods=['POST'])
@login_required
def secure_panel():
    domain = request.form.get('domain')
    email = request.form.get('email', 'admin@alamor.local')
    
    # 1. دریافت SSL
    success, msg = generate_letsencrypt_cert(domain, email)
    if not success:
        return jsonify({'status': 'error', 'message': msg})
    
    # 2. تولید مسیر رندوم (مثلاً admin_a3f9)
    random_suffix = secrets.token_hex(3)
    secret_path = f"admin_{random_suffix}"
    
    # 3. تنظیم Nginx
    setup_success, cert_path = setup_secure_panel_nginx(domain, secret_path)
    
    if setup_success:
        # 4. ریستارت سرویس پنل برای اعمال مسیر جدید
        def restart_server():
            time.sleep(2) # صبر برای ارسال پاسخ به کلاینت
            os.system("systemctl restart alamor")
            
        threading.Thread(target=restart_server).start()
        
        new_url = f"https://{domain}/{secret_path}/dashboard"
        return jsonify({
            'status': 'ok', 
            'new_url': new_url,
            'cert_path': cert_path,
            'message': 'Security applied! Redirecting...'
        })
    else:
        return jsonify({'status': 'error', 'message': cert_path})