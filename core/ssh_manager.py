# AlamorTunnel/core/ssh_manager.py
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
        client.connect(ip, port=int(port), username=user, password=password, timeout=10, banner_timeout=10)
        client.close()
        return True
    except Exception as e:
        print(f"[SSH Error] Verify failed: {e}")
        return False

def run_remote_command(ip, command, retries=3):
    from core.database import get_connected_server
    server = get_connected_server()
    if not server: return False, "No server connected"
    
    # سرور: (ip, user, password, port)
    target_ip, user, password, port = server[0], server[1], server[2], int(server[3])
    
    for attempt in range(retries):
        client = create_client()
        try:
            # تنظیمات برای پایداری بیشتر
            client.connect(
                target_ip, 
                port=port, 
                username=user, 
                password=password, 
                timeout=15,          # تایم‌اوت اتصال
                banner_timeout=15,   # تایم‌اوت بنر
                auth_timeout=15      # تایم‌اوت احراز هویت
            )
            
            # فعال‌سازی KeepAlive برای جلوگیری از قطع شدن در دستورات طولانی
            transport = client.get_transport()
            transport.set_keepalive(30)
            
            stdin, stdout, stderr = client.exec_command(command, timeout=60)
            
            # خواندن خروجی
            exit_status = stdout.channel.recv_exit_status() # صبر تا پایان دستور
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            client.close()
            
            if exit_status == 0:
                return True, output
            else:
                # اگر در stderr چیزی نبود ولی استاتوس ارور بود، خروجی رو به عنوان ارور برگردون
                return False, error if error else output

        except (socket.error, paramiko.SSHException) as e:
            print(f"[SSH Warning] Attempt {attempt+1}/{retries} failed: {e}")
            time.sleep(2) # صبر قبل از تلاش مجدد
            continue
        except Exception as e:
            return False, str(e)
            
    return False, "Connection timed out after multiple retries."