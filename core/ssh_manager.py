import paramiko
import time
import socket

# 1. کلاس اصلی (با قابلیت PTY برای نصب موفق)
class SSHManager:
    def run_remote_command(self, ip, user, password, command, port=22):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            client.connect(
                ip, 
                port=int(port), 
                username=user, 
                password=password, 
                timeout=20, 
                banner_timeout=20,
                allow_agent=False, 
                look_for_keys=False
            )
            
            # فعال سازی PTY برای جلوگیری از قطع شدن
            stdin, stdout, stderr = client.exec_command(command, get_pty=True)
            
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            
            exit_status = stdout.channel.recv_exit_status()
            client.close()

            full_output = f"{out}\n{err}".strip()
            
            if exit_status != 0:
                return False, f"Exit Code {exit_status}: {full_output}"
            
            return True, full_output

        except socket.timeout:
            return False, "SSH Connection Timed Out"
        except paramiko.AuthenticationException:
            return False, "SSH Authentication Failed"
        except Exception as e:
            return False, f"SSH Error: {str(e)}"

# ========================================================
# 2. توابع سازگاری (برای جلوگیری از ارور در سایر فایل‌ها)
# ========================================================

def verify_ssh_connection(ip, user, password, port=22):
    """
    مورد استفاده در dashboard.py
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            ip, 
            port=int(port), 
            username=user, 
            password=password, 
            timeout=5,
            allow_agent=False,
            look_for_keys=False
        )
        client.close()
        return True
    except:
        return False

def run_remote_command(ip, user, password, command, port=22):
    """
    مورد استفاده در backhaul_manager.py
    این تابع درخواست‌های قدیمی را به کلاس جدید وصل می‌کند.
    """
    manager = SSHManager()
    return manager.run_remote_command(ip, user, password, command, port)