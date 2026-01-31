import paramiko

def verify_ssh_connection(ip, user, password, port=22):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(ip, port=port, username=user, password=password, timeout=5)
        client.close()
        return True
    except:
        return False

def run_remote_command(ip, command):
    from core.database import get_connected_server
    server = get_connected_server()
    if not server: return False, "No server connected"
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(server[0], port=server[3], username=server[1], password=server[2], timeout=10)
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()
        client.close()
        return True, output if not error else error
    except Exception as e:
        return False, str(e)