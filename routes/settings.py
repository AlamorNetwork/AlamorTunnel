from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from core.database import update_password
from routes.auth import login_required

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password and new_password == confirm_password:
            try:
                update_password(new_password)
                flash('Administrator password updated successfully.', 'success')
            except Exception as e:
                flash(f'Error updating password: {e}', 'danger')
        else:
            flash('Passwords do not match or are empty.', 'danger')
            
    return render_template('settings.html')