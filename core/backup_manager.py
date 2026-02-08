import os
import secrets
import logging
from core.ssh_manager import SSHManager

logger = logging.getLogger("BackhaulManager")
REMOTE_BIN = "/root/alamor/bin/backhaul"
REMOTE_CFG = "/root/alamor/bin/backhaul_server.toml"
LOCAL_BIN = "/root/AlamorTunnel/bin/backhaul"
DL_URL = "https://github.com/Musixal/Backhaul/releases/download/v0.6.0/backhaul_linux_amd64.tar.gz"

class BackhaulManager:
    def _gen_token(self): return secrets.token_hex(16)

    def _server_toml(self, c):
        mux = f"\n    mux_con = {c.get('mux_con',8)}\n    mux_version = 1" if "mux" in c['transport'] else ""
        tls = '\n    tls_cert = "/root/alamor/certs/server.crt"\n    tls_key = "/root/alamor/certs/server.key"' if "wss" in c['transport'] else ""
        ports = ",".join([f'"{p.strip()}"' for p in c.get('port_rules',[]) if p.strip()])
        
        return f"""[server]
    bind_addr = "0.0.0.0:{c['tunnel_port']}"
    transport = "{c['transport']}"
    token = "{c.get('token', self._gen_token())}"
    keepalive_period = {c.get('keepalive', 75)}
    nodelay = true
    heartbeat = 40
    sniffer = {str(c.get('sniffer', False)).lower()}
    web_port = {c.get('web_port', 2060)}
    log_level = "info"
    {mux}
    {tls}
    ports = [{ports}]
    """, c.get('token')

    def _client_toml(self, ip, c):
        mux = f"\n    mux_version = 1" if "mux" in c['transport'] else ""
        return f"""[client]
    remote_addr = "{ip}:{c['tunnel_port']}"
    transport = "{c['transport']}"
    token = "{c['token']}"
    connection_pool = {c.get('pool', 8)}
    aggressive_pool = {str(c.get('aggressive', False)).lower()}
    keepalive_period = 75
    nodelay = true
    retry_interval = 3
    {mux}
    """

    def install_server(self, ip, c):
        ssh = SSHManager()
        run = lambda cmd: ssh.run_remote_command(ip, c.get('ssh_user','root'), c.get('ssh_pass'), cmd, c.get('ssh_port',22), c.get('ssh_key'))
        
        run("mkdir -p /root/alamor/bin /root/alamor/certs")
        
        # --- بخش اصلاح شده (FIXED) ---
        # این دستور چک میکند اگر فایل دانلود نشده، دانلود کند
        # و در زمان تغییر نام، اگر فایل هم‌نام بود ارور ندهد
        install_cmd = f"""
        if [ ! -f {REMOTE_BIN} ]; then
            curl -L -k -o /tmp/bh.tar.gz {DL_URL}
            tar -xzf /tmp/bh.tar.gz -C /root/alamor/bin/
            # اگر فایل با نام قدیمی بود، تغییر نام بده
            if [ -f /root/alamor/bin/backhaul_linux_amd64 ]; then
                mv /root/alamor/bin/backhaul_linux_amd64 {REMOTE_BIN}
            fi
            chmod +x {REMOTE_BIN}
        fi
        """
        run(install_cmd)
        # -----------------------------
        
        if "wss" in c['transport']:
            run("openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 -subj '/CN=bing.com' -keyout /root/alamor/certs/server.key -out /root/alamor/certs/server.crt")
            
        toml, token = self._server_toml(c)
        c['token'] = token
        run(f"cat <<EOF > {REMOTE_CFG}\n{toml}\nEOF")
        
        svc = f"[Unit]\nDescription=Backhaul\n[Service]\nExecStart={REMOTE_BIN} -c {REMOTE_CFG}\nRestart=always\n[Install]\nWantedBy=multi-user.target"
        run(f"cat <<EOF > /etc/systemd/system/backhaul.service\n{svc}\nEOF")
        run("systemctl daemon-reload && systemctl restart backhaul && systemctl enable backhaul")
        return True, "Installed"

    def install_client(self, ip, c):
        # دانلود نسخه کلاینت (لوکال)
        if not os.path.exists(LOCAL_BIN):
             os.makedirs(os.path.dirname(LOCAL_BIN), exist_ok=True)
             os.system(f"curl -L -k -o /tmp/bh.tar.gz {DL_URL}")
             os.system(f"tar -xzf /tmp/bh.tar.gz -C /root/AlamorTunnel/bin/")
             if os.path.exists("/root/AlamorTunnel/bin/backhaul_linux_amd64"):
                 os.system(f"mv /root/AlamorTunnel/bin/backhaul_linux_amd64 {LOCAL_BIN}")
             os.system(f"chmod +x {LOCAL_BIN}")

        toml = self._client_toml(ip, c)
        path = f"/root/AlamorTunnel/bin/backhaul_client_{c['tunnel_port']}.toml"
        with open(path, "w") as f: f.write(toml)
        
        svc = f"[Unit]\nDescription=BH Client {c['tunnel_port']}\n[Service]\nExecStart={LOCAL_BIN} -c {path}\nRestart=always\n[Install]\nWantedBy=multi-user.target"
        with open(f"/etc/systemd/system/backhaul-client-{c['tunnel_port']}.service", "w") as f: f.write(svc)
        os.system(f"systemctl daemon-reload && systemctl restart backhaul-client-{c['tunnel_port']}")
        return True, "Installed"

def install_remote_backhaul(ip, iran, c): return BackhaulManager().install_server(ip, c)
def install_local_backhaul(c): return BackhaulManager().install_client(c['ssh_ip'], c)
def generate_token(): return secrets.token_hex(16)
def stop_and_delete_backhaul(port): os.system(f"systemctl stop backhaul-client-{port}")
# =========================================================
# GLOBAL HELPERS (Required by routes/tunnels.py)
# =========================================================

def generate_token():
    return secrets.token_hex(16)

def stop_and_delete_backhaul(port):
    # در معماری Reverse، سرور روی ایران است
    service_name = f"backhaul-server-{port}"
    os.system(f"systemctl stop {service_name}")
    os.system(f"systemctl disable {service_name}")
    os.system(f"rm -f /etc/systemd/system/{service_name}.service")
    os.system("systemctl daemon-reload")