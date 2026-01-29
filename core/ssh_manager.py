import paramiko
import os
import socket

# مسیر کلید SSH
SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_rsa')

def generate_ssh_key():
    """اگر کلید وجود نداشت، می‌سازد"""
    if not os.path.exists(SSH_KEY_PATH):
        print(f"[+] Generating SSH Key at {SSH_KEY_PATH}")
        os.system(f'ssh-keygen -t rsa -b 4096 -f {SSH_KEY_PATH} -N ""')

def setup_passwordless_ssh(ip, password, port=22, user='root'):
    """اتصال اولیه و کپی کردن کلید در سرور مقصد"""
    generate_ssh_key()
    
    # خواندن کلید عمومی
    try:
        with open(f"{SSH_KEY_PATH}.pub", "r") as f:
            public_key = f.read().strip()
    except FileNotFoundError:
        return False, "SSH Public Key not found. Generation failed."
    
    try:
        # ایجاد کلاینت
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # اتصال با پسورد
        print(f"[~] Connecting to {ip}:{port}...")
        client.connect(hostname=ip, port=int(port), username=user, password=password, timeout=10)
        
        # دستور تزریق کلید (با بررسی اینکه تکراری نباشد)
        cmd = f'mkdir -p ~/.ssh && grep -q "{public_key}" ~/.ssh/authorized_keys || echo "{public_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
        
        stdin, stdout, stderr = client.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        
        client.close()
        
        if exit_status == 0:
            return True, "Connection successful! SSH Key deployed."
        else:
            return False, f"Remote Error: {stderr.read().decode()}"

    except paramiko.AuthenticationException:
        return False, "Authentication Failed: Wrong Password."
    except socket.timeout:
        return False, "Connection Timeout: Server unreachable."
    except Exception as e:
        return False, f"Error: {str(e)}"

def run_remote_command(ip, command, user='root', port=22):
    """اجرای دستور در سرور خارج بدون پسورد"""
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=ip, port=int(port), username=user, key_filename=SSH_KEY_PATH, timeout=5)
        
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        client.close()
        
        if error and not output:
            return False, error
        return True, output
    except Exception as e:
        return False, str(e)