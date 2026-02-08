import paramiko
import time
import socket
import logging

# تنظیم لاگر
logger = logging.getLogger("SSHManager")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - [SSH] - %(message)s'))
    logger.addHandler(handler)

class SSHManager:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def run_remote_command(self, ip, user, password, command, port=22):
        """
        اجرای دستور روی سرور ریموت با مدیریت خطا و PTY
        """
        try:
            logger.info(f"Connecting to {ip}:{port}...")
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
            
            # استفاده از PTY برای جلوگیری از قطع شدن دستورات توسط سرور
            stdin, stdout, stderr = self.client.exec_command(command, get_pty=True)
            
            # خواندن خروجی‌ها
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            
            exit_status = stdout.channel.recv_exit_status()
            self.client.close()

            full_output = f"{out}\n{err}".strip()
            
            if exit_status != 0:
                logger.error(f"Command Failed: {full_output}")
                return False, f"Exit Code {exit_status}: {full_output}"
            
            logger.info("Command Executed Successfully")
            return True, full_output

        except socket.timeout:
            return False, "SSH Connection Timed Out"
        except paramiko.AuthenticationException:
            return False, "SSH Authentication Failed"
        except Exception as e:
            return False, f"SSH Error: {str(e)}"

# ==========================================================
# توابع کمکی (Wrapper Functions) برای سازگاری با کدهای قدیمی
# ==========================================================

def verify_ssh_connection(ip, user, password, port=22):
    """بررسی سریع اتصال (استفاده شده در داشبورد)"""
    manager = SSHManager()
    return manager.run_remote_command(ip, user, password, "whoami", port)[0]

def run_remote_command(ip, user, password, command, port=22):
    """تابع عمومی اجرا (استفاده شده در سایر ماژول‌ها)"""
    manager = SSHManager()
    return manager.run_remote_command(ip, user, password, command, port)