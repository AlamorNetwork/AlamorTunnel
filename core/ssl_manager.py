import paramiko
import os
import socket

SSH_KEY_PATH = os.path.expanduser('~/.ssh/id_rsa')

def generate_ssh_key():
    if not os.path.exists(SSH_KEY_PATH):
        os.system(f'ssh-keygen -t rsa -b 4096 -f {SSH_KEY_PATH} -N ""')

def setup_passwordless_ssh(ip, password, port=22, user='root'):
    generate_ssh_key()
    
    with open(f"{SSH_KEY_PATH}.pub", "r") as f:
        public_key = f.read().strip()
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=ip, port=int(port), username=user, password=password, timeout=10)
        
        cmd = f'mkdir -p ~/.ssh && grep -q "{public_key}" ~/.ssh/authorized_keys || echo "{public_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
        
        stdin, stdout, stderr = client.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        client.close()
        
        if exit_status == 0:
            return True, "Key deployed successfully."
        else:
            return False, f"Server Error: {stderr.read().decode()}"

    except Exception as e:
        return False, str(e)

def run_remote_command(ip, command):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=ip, key_filename=SSH_KEY_PATH, timeout=5)
        stdin, stdout, stderr = client.exec_command(command)
        return True, stdout.read().decode().strip()
    except Exception as e:
        return False, str(e)