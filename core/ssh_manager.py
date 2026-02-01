import paramiko
import time
import socket

def create_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client

def verify_ssh_connection(ip, user, password, port=22):
    client = create_client()
    try:
        client.connect(ip, port=int(port), username=user, password=password, timeout=10)
        client.close()
        return True
    except Exception as e:
        print(f"[SSH Error] {e}")
        return False

def run_remote_command(ip, command):
    """اجرای دستور معمولی (انتظار تا پایان)"""
    from core.database import get_connected_server
    server = get_connected_server()
    if not server: return False, "No server connected"
    
    try:
        client = create_client()
        port = int(server[3])
        client.connect(server[0], port=port, username=server[1], password=server[2], timeout=15)
        
        # Keepalive
        transport = client.get_transport()
        transport.set_keepalive(30)
        
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        client.close()
        
        if exit_status == 0:
            return True, output
        else:
            return False, error if error else output
    except Exception as e:
        return False, str(e)

def run_remote_command_iter(ip, command):
    """
    اجرای دستور طولانی با بازگرداندن خروجی به صورت زنده (Generator)
    مناسب برای Slipstream که بیلد طولانی دارد.
    """
    from core.database import get_connected_server
    server = get_connected_server()
    if not server: 
        yield f"Error: No server connected"
        return

    try:
        client = create_client()
        port = int(server[3])
        
        client.connect(server[0], port=port, username=server[1], password=server[2], timeout=15)
        
        # تنظیم Keepalive حیاتی برای جلوگیری از قطع شدن وسط بیلد
        transport = client.get_transport()
        transport.set_keepalive(30) 
        
        # get_pty=True باعث می‌شود خروجی بافر نشود و سریع دیده شود
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        
        # خواندن خط به خط
        for line in iter(stdout.readline, ""):
            yield line.strip()
            
        client.close()
    except Exception as e:
        yield f"SSH Critical Error: {str(e)}"