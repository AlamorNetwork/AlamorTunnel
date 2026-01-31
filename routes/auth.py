from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from core.database import verify_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if verify_user(username, password):
            session['user'] = username
            session.permanent = True
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid Credentials', 'danger')
            
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))