from flask import Blueprint, render_template, request, jsonify
from core.ssl_manager import check_domain_dns, generate_letsencrypt_cert, setup_fake_site_nginx
from core.scanner import scan_for_clean_ip
from routes.auth import login_required
import time

domains_bp = Blueprint('domains', __name__)

@domains_bp.route('/domains')
@login_required
def index():
    return render_template('domains.html')

@domains_bp.route('/domains/check-dns', methods=['POST'])
@login_required
def check_dns():
    domain = request.form.get('domain')
    
    time.sleep(1) # تاخیر نمایشی برای حس هکری
    
    # تابع جدید ما حالا دو مقدار برمی‌گرداند: موفقیت و پیام
    is_valid, message = check_domain_dns(domain)
    
    if is_valid:
        return jsonify({'status': 'ok', 'message': 'Domain verification successful.'})
    else:
        # پیام خطا دقیقاً می‌گوید چه چیزی با چه چیزی مغایرت دارد
        return jsonify({'status': 'error', 'message': message})

@domains_bp.route('/domains/scan-ips', methods=['POST'])
@login_required
def scan_ips():
    domain = request.form.get('domain')
    if not domain: return jsonify({'status': 'error', 'message': 'No domain provided'})
    ips, logs = scan_for_clean_ip(domain)
    return jsonify({'status': 'ok', 'ips': ips, 'logs': logs})

@domains_bp.route('/domains/get-cert', methods=['POST'])
@login_required
def get_cert():
    domain = request.form.get('domain')
    email = request.form.get('email', 'admin@alamor.local')
    success, msg = generate_letsencrypt_cert(domain, email)
    if success:
        setup_fake_site_nginx(domain)
        return jsonify({'status': 'ok', 'message': msg})
    else:
        return jsonify({'status': 'error', 'message': msg})