from flask import Blueprint, render_template, request, jsonify
from core.ssl_manager import check_domain_dns, generate_letsencrypt_cert, setup_fake_site_nginx
from routes.auth import login_required

domains_bp = Blueprint('domains', __name__)

@domains_bp.route('/domains')
@login_required
def index():
    return render_template('domains.html')

@domains_bp.route('/domains/check-dns', methods=['POST'])
@login_required
def check_dns():
    domain = request.form.get('domain')
    if check_domain_dns(domain):
        return jsonify({'status': 'ok', 'message': 'Domain points to this server!'})
    else:
        return jsonify({'status': 'error', 'message': 'DNS record not found or IP mismatch.'})

@domains_bp.route('/domains/get-cert', methods=['POST'])
@login_required
def get_cert():
    domain = request.form.get('domain')
    email = request.form.get('email', 'admin@alamor.local')
    
    success, msg = generate_letsencrypt_cert(domain, email)
    if success:
        # اگر موفق بود، سایت فیک را هم بالا می‌آوریم
        setup_fake_site_nginx(domain)
        return jsonify({'status': 'ok', 'message': msg})
    else:
        return jsonify({'status': 'error', 'message': msg})