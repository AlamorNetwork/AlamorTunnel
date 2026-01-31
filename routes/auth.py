# AlamorTunnel/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from core.database import check_user
import functools

auth_bp = Blueprint('auth', __name__)

def login_required(view):
    """دکوریتور برای محدود کردن دسترسی به کاربران لاگین شده"""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # اگر کاربر قبلا لاگین بود، مستقیم برود به داشبورد
    if 'user' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            # بررسی اعتبار سنجی در دیتابیس
            user = check_user(username, password)
            
            if user:
                session.permanent = True  # فعال سازی ماندگاری سشن
                session['user'] = user[0]
                flash(f'Welcome back, {username}!', 'success')
                return redirect(url_for('dashboard.index'))
            else:
                flash('Invalid credentials. Please try again.', 'danger')
        except Exception as e:
            flash(f'System Error: {str(e)}', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))