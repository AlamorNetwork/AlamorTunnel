from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from core.database import check_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # چک کردن یوزر با دیتابیس
        user = check_user(username, password)
        
        if user:
            session['user'] = user[0]  # ذخیره سشن
            return redirect(url_for('dashboard.index'))
        else:
            flash('نام کاربری یا رمز عبور اشتباه است', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth.login'))