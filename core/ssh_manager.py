import paramiko
import time
import socket

# نکته مهم: اینجا دیگر from core.database import ... نداریم تا ارور چرخشی رفع شود.

class SSHManager:
    def __init__(self):
        self.client = None

    def _create_client(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    def run_remote_command(self, ip, username, password, command, port=22):
        """اجرای دستور روی سرور مشخص با دریافت مشخصات کامل"""
        client = self._create_client()
        try:
            client.connect(ip, port=int(port), username=username, password=password, timeout=15)
            
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

# --- توابع قدیمی (برای جلوگیری از شکستن سایر بخش‌های برنامه) ---

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
    """
    نسخه قدیمی تابع برای سازگاری با کدهای قبلی
    """
    # ایمپورت را اینجا انجام می‌دهیم تا ارور Circular Import رفع شود
    from core.database import get_connected_server
    
    server = get_connected_server()
    if not server: return False, "No server connected"
    
    manager = SSHManager()
    # فرض بر این است که پورت در ایندکس 3 است
    return manager.run_remote_command(server[0], server[1], server[2], command, server[3])

def run_remote_command_iter(ip, command):
    """
    اجرای دستور طولانی با خروجی زنده (Generator)
    """
    # ایمپورت را اینجا انجام می‌دهیم تا ارور Circular Import رفع شود
    from core.database import get_connected_server
    
    server = get_connected_server()
    if not server: 
        yield f"Error: No server connected"
        return

    try:
        client = create_client()
        port = int(server[3])
        
        client.connect(server[0], port=port, username=server[1], password=server[2], timeout=15)
        
        transport = client.get_transport()
        transport.set_keepalive(30) 
        
        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        
        for line in iter(stdout.readline, ""):
            yield line.strip()
            
        client.close()
    except Exception as e:
        yield f"SSH Critical Error: {str(e)}"