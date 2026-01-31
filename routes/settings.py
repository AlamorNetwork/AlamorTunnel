from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from core.database import update_password

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        if 'new_password' in request.form:
            update_password(session['user'], request.form['new_password'])
            flash('Password updated successfully.', 'success')
            
    return render_template('settings.html')