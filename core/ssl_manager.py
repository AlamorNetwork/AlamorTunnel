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
        client.connect(ip, port=int(port), username=user, password=password, timeout=10)
        client.close()
        return True
    except Exception as e:
        print(f"[SSH Error] {e}")
        return False

def run_remote_command(ip, command, retries=2):
    # ایمپورت داخل تابع برای جلوگیری از خطای Circular Import
    from core.database import get_connected_server
    
    server = get_connected_server()
    if not server: return False, "No server connected in database."
    
    # دیتابیس: (ip, user, password, port)
    target_ip, user, password, port = server[0], server[1], server[2], int(server[3])
    
    # اگر IP ورودی با دیتابیس فرق داشت (برای اطمینان)
    if ip and ip != target_ip:
        print(f"[SSH Warning] IP Mismatch: Req={ip} vs DB={target_ip}")
    
    last_error = ""
    for attempt in range(retries):
        client = create_client()
        try:
            client.connect(target_ip, port=port, username=user, password=password, timeout=15)
            
            # اجرای دستور
            stdin, stdout, stderr = client.exec_command(command, timeout=60)
            
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            client.close()
            
            if exit_status == 0:
                return True, output
            else:
                return False, error if error else output

        except Exception as e:
            last_error = str(e)
            time.sleep(1)
            continue
            
    return False, f"SSH Failed: {last_error}"