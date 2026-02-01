import paramiko
import time
import socket

def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client

def verify_ssh_connection(ip, user, password, port=22):
    """بررسی اتصال SSH بدون اجرای دستور"""
    client = create_client()
    try:
        client.connect(ip, port=int(port), username=user, password=password, timeout=10, banner_timeout=10)
        client.close()
        return True
    except Exception as e:
        print(f"[SSH Error] Verify failed: {e}")
        return False

def run_remote_command(ip, command):
    from core.database import get_connected_server
    server = get_connected_server()
    if not server: return False, "No server connected"
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # FIX: Force port to be int
        ssh_port = int(server[3])
        
        client.connect(server[0], port=ssh_port, username=server[1], password=server[2], timeout=10)
        
        # ... ادامه کد ...
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        client.close()
        return True, output if not error else error
    except Exception as e:
        return False, str(e)