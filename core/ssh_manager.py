import paramiko
import time
import socket

class SSHManager:
    def run_remote_command(self, ip, user, password, command, port=22):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # اتصال با تایم‌اوت مشخص
            client.connect(ip, port=int(port), username=user, password=password, timeout=10, banner_timeout=10)
            
            # اجرای دستور
            # get_pty=False برای جلوگیری از کاراکترهای عجیب ترمینال
            stdin, stdout, stderr = client.exec_command(command, get_pty=False)
            
            # خواندن خروجی‌ها
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            
            exit_status = stdout.channel.recv_exit_status()
            client.close()

            # ترکیب خروجی و ارور برای دیباگ بهتر
            full_output = f"{out}\n{err}".strip()
            
            if exit_status != 0:
                # اگر دستور با خطا بسته شد
                return False, f"Exit Code {exit_status}: {full_output}"
            
            return True, full_output

        except socket.timeout:
            return False, "SSH Connection Timed Out"
        except paramiko.AuthenticationException:
            return False, "SSH Authentication Failed (Wrong Password)"
        except paramiko.SSHException as e:
            return False, f"SSH Protocol Error: {str(e)}"
        except Exception as e:
            return False, f"General Error: {str(e)}"