import paramiko
import time
import socket
import logging

# تنظیمات لاگ برای دیباگ دقیق‌تر
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SSHManager")

class SSHManager:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def run_remote_command(self, ip, user, password, command, port=22):
        """
        اجرای دستور روی سرور ریموت با قابلیت PTY برای جلوگیری از قطع شدن
        """
        try:
            self.client.connect(
                ip, 
                port=int(port), 
                username=user, 
                password=password, 
                timeout=20, 
                banner_timeout=20,
                allow_agent=False, 
                look_for_keys=False
            )
            
            # نکته حیاتی: get_pty=True باعث می‌شود سرور ارتباط را قطع نکند
            stdin, stdout, stderr = self.client.exec_command(command, get_pty=True)
            
            # خواندن خروجی‌ها
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            
            exit_status = stdout.channel.recv_exit_status()
            self.client.close()

            full_output = f"{out}\n{err}".strip()
            
            if exit_status != 0:
                logger.error(f"Command failed on {ip}: {full_output}")
                return False, f"Exit Code {exit_status}: {full_output}"
            
            return True, full_output

        except socket.timeout:
            return False, "SSH Connection Timed Out"
        except paramiko.AuthenticationException:
            return False, "SSH Authentication Failed (Wrong Password)"
        except Exception as e:
            return False, f"SSH Error: {str(e)}"

# ========================================================
# توابع کمکی (Wrapper Functions)
# برای سازگاری با بخش‌های مختلف پنل (Dashboard, Backhaul)
# ========================================================

def verify_ssh_connection(ip, user, password, port=22):
    """
    بررسی سریع اتصال برای نمایش در داشبورد (سبز/قرمز)
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
            banner_timeout=5,
            allow_agent=False,
            look_for_keys=False
        )
        client.close()
        return True
    except:
        return False

def run_remote_command(ip, user, password, command, port=22):
    """
    تابع عمومی برای استفاده در سایر فایل‌ها بدون نیاز به ساخت کلاس
    """
    manager = SSHManager()
    return manager.run_remote_command(ip, user, password, command, port)