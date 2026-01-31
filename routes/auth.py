from flask import Blueprint, render_template, request, redirect, url_for, flash, session
# تغییر مهم: استفاده از check_user به جای verify_user
from core.database import check_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # بررسی صحت نام کاربری و رمز عبور
        user = check_user(username, password)
        
        if user:
            session['user'] = user[0]  # ذخیره نام کاربری در سشن
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))