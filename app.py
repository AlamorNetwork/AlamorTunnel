from flask import Flask, render_template, request, redirect, session, url_for, flash
from core.database import init_db, verify_user, update_password, create_initial_user, add_or_update_server, get_connected_server
# ایمپورت ماژول‌های جدید
from core.ssh_manager import setup_passwordless_ssh, run_remote_command
import os
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# راه اندازی دیتابیس
try:
    init_db()
    create_initial_user()
except Exception as e:
    print(f"Database Error: {e}")

def is_logged_in():
    return 'user' in session

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if verify_user(username, password):
            session['user'] = username
            session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            flash('Login Failed: Check credentials', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    server_info = get_connected_server()
    return render_template('dashboard.html', user=session['user'], server=server_info)

@app.route('/connect-server', methods=['POST'])
def connect_server():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    ip = request.form.get('ip')
    password = request.form.get('password')
    port = request.form.get('port', 22)
    
    # استفاده از ماژول SSH
    try:
        success, message = setup_passwordless_ssh(ip, password, port)
        if success:
            add_or_update_server(ip, port, 'root', 'connected')
            flash(f'Success: {message}', 'success')
        else:
            flash(f'Connection Failed: {message}', 'danger')
    except Exception as e:
        flash(f'System Error: {str(e)}', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'new_password' in request.form:
            new_pass = request.form['new_password']
            update_password(session['user'], new_pass)
            flash('Password updated.', 'success')
            
    return render_template('settings.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # اجرا روی پورت 5050
    app.run(host='0.0.0.0', port=5050, debug=True)