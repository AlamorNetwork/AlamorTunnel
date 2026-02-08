import paramiko
import time
import socket
import logging
import io

logger = logging.getLogger("SSHManager")

class SSHManager:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def run_remote_command(self, ip, user, password, command, port=22, ssh_key=None):
        try:
            logger.info(f"Connecting to {ip}:{port}...")
            
            pkey = None
            if ssh_key and ssh_key.strip():
                try:
                    pkey = paramiko.RSAKey.from_private_key(io.StringIO(ssh_key))
                except paramiko.SSHException:
                    try:
                        pkey = paramiko.Ed25519Key.from_private_key(io.StringIO(ssh_key))
                    except:
                        logger.warning("Could not parse SSH Key, falling back to password.")

            self.client.connect(
                ip, 
                port=int(port), 
                username=user, 
                password=password, 
                pkey=pkey,
                timeout=20,
                allow_agent=False, 
                look_for_keys=False
            )
            
            stdin, stdout, stderr = self.client.exec_command(command, get_pty=True)
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            exit_status = stdout.channel.recv_exit_status()
            self.client.close()

            full_output = f"{out}\n{err}".strip()
            
            if exit_status != 0:
                logger.error(f"Command Failed: {full_output}")
                return False, f"Exit Code {exit_status}: {full_output}"
            
            return True, full_output

        except Exception as e:
            logger.error(f"SSH Connection Error: {e}")
            return False, f"SSH Error: {str(e)}"


def run_remote_command(ip, user, password, command, port=22, ssh_key=None):
    return SSHManager().run_remote_command(ip, user, password, command, port, ssh_key)

def verify_ssh_connection(ip, user, password, port=22, ssh_key=None):
    # Try a simple command to verify connection
    return run_remote_command(ip, user, password, "whoami", port, ssh_key)[0]