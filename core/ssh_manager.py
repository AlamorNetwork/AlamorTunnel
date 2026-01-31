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

def run_remote_command(ip, command, retries=3):
    """
    اجرای دستور روی سرور خارج با قابلیت تلاش مجدد و KeepAlive.
    نکته: ایمپورت دیتابیس داخل تابع است تا از Circular Import جلوگیری شود.
    """
    # LOCAL IMPORT - حیاتی برای جلوگیری از خطا
    from core.database import get_connected_server
    
    server = get_connected_server()
    if not server: return False, "No server connected in database."
    
    # استخراج اطلاعات از دیتابیس: (ip, user, password, port)
    target_ip, user, password, port = server[0], server[1], server[2], int(server[3])
    
    # لاگ هشدار اگر آی‌پی درخواستی با دیتابیس فرق داشت
    if ip and ip != target_ip:
        print(f"[SSH Warning] Request IP ({ip}) mismatch with DB IP ({target_ip}). Using DB IP.")
    
    last_error = ""
    for attempt in range(retries):
        client = create_client()
        try:
            client.connect(
                target_ip, 
                port=port, 
                username=user, 
                password=password, 
                timeout=15,
                banner_timeout=15,
                auth_timeout=15
            )
            
            # فعال‌سازی KeepAlive
            transport = client.get_transport()
            transport.set_keepalive(30)
            
            # اجرای دستور
            stdin, stdout, stderr = client.exec_command(command, timeout=60)
            
            # دریافت خروجی
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            client.close()
            
            if exit_status == 0:
                return True, output
            else:
                # اگر خروجی استاندارد داریم اما خطا هم داریم، خطا اولویت دارد
                return False, error if error else output

        except (socket.error, paramiko.SSHException) as e:
            last_error = str(e)
            print(f"[SSH Warning] Attempt {attempt+1}/{retries} failed: {e}")
            time.sleep(2)
            continue
        except Exception as e:
            return False, str(e)
            
    return False, f"SSH Connection Failed after {retries} retries. Error: {last_error}"