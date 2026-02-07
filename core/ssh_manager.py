import paramiko
import time
import socket

class SSHManager:
    def run_remote_command(self, ip, user, password, command, port=22):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # تنظیمات اتصال دقیقاً مثل اسکریپت تست موفق
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
            
            # نکته طلایی: فعال کردن PTY برای جلوگیری از قطع شدن
            stdin, stdout, stderr = client.exec_command(command, get_pty=True)
            
            # خواندن خروجی به صورت کامل
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            
            exit_status = stdout.channel.recv_exit_status()
            client.close()

            # ترکیب خروجی‌ها
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