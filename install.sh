#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}>>> ALAMOR TUNNEL INSTALLER (DEBUG MODE) <<<${NC}"

# 1. Check Root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run as root!${NC}"
  exit
fi

# 2. Update & Install Dependencies
echo -e "${GREEN}[+] Updating System & Installing Dependencies...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl wget unzip tar iptables-persistent net-tools build-essential

# 3. Create Directories
echo -e "${GREEN}[+] Creating Directory Structure...${NC}"
mkdir -p /root/AlamorTunnel/bin
mkdir -p /root/AlamorTunnel/configs
mkdir -p /root/AlamorTunnel/logs
mkdir -p /root/certs
chmod -R 755 /root/AlamorTunnel

# 4. Install Python Libraries
echo -e "${GREEN}[+] Installing Python Requirements...${NC}"
pip3 install Flask==3.0.0 Flask-Login==0.6.3 Werkzeug==3.0.1 gunicorn==21.2.0 requests==2.31.0 psutil==5.9.6 paramiko==3.4.0 PyYAML==6.0.1 schedule==1.2.1 colorama==0.4.6 tqdm==4.66.1 cryptography==41.0.7 netifaces==0.11.0 --break-system-packages

# 5. Download Cores
echo -e "${GREEN}[+] Downloading Tunnel Cores...${NC}"
BIN_DIR="/root/AlamorTunnel/bin"

# Hysteria 2
if [ ! -f "$BIN_DIR/hysteria" ]; then
    echo "--> Downloading Hysteria..."
    curl -L -k -o $BIN_DIR/hysteria https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64
    chmod +x $BIN_DIR/hysteria
fi

# Backhaul
if [ ! -f "$BIN_DIR/backhaul" ]; then
    echo "--> Downloading Backhaul..."
    curl -L -k -o $BIN_DIR/backhaul.tar.gz https://github.com/Musixal/Backhaul/releases/download/v0.6.0/backhaul_linux_amd64.tar.gz
    tar -xzf $BIN_DIR/backhaul.tar.gz -C $BIN_DIR
    mv $BIN_DIR/backhaul_linux_amd64 $BIN_DIR/backhaul 2>/dev/null || true
    chmod +x $BIN_DIR/backhaul
    rm $BIN_DIR/backhaul.tar.gz
fi

# Rathole
if [ ! -f "$BIN_DIR/rathole" ]; then
    echo "--> Downloading Rathole..."
    curl -L -k -o $BIN_DIR/rathole.zip https://github.com/rapiz1/rathole/releases/latest/download/rathole-x86_64-unknown-linux-gnu.zip
    unzip -o $BIN_DIR/rathole.zip -d $BIN_DIR
    chmod +x $BIN_DIR/rathole
    rm $BIN_DIR/rathole.zip
fi

# Gost
if [ ! -f "$BIN_DIR/gost" ]; then
    echo "--> Downloading Gost..."
    curl -L -k -o $BIN_DIR/gost.gz https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz
    gzip -d -f $BIN_DIR/gost.gz
    chmod +x $BIN_DIR/gost
fi

# 6. Initialize Database
echo -e "${GREEN}[+] Initializing Database...${NC}"
cd /root/AlamorTunnel
python3 -c "from core.database import init_db; init_db(); print('Database initialized.')"

# 7. Create Service (With Output Logging)
echo -e "${GREEN}[+] Creating Systemd Service...${NC}"
cat > /etc/systemd/system/alamor.service <<EOL
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=/root/AlamorTunnel
# PYTHONUNBUFFERED=1 باعث میشه لاگ‌ها سریع نشون داده بشن
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

# 8. Start Services
echo -e "${GREEN}[+] Starting Panel...${NC}"
systemctl daemon-reload
systemctl enable alamor
systemctl restart alamor

echo -e "${YELLOW}----------------------------------------------------${NC}"
echo -e "${GREEN} INSTALLATION COMPLETE! ${NC}"
echo -e "${CYAN} View Logs: journalctl -u alamor -f ${NC}"
echo -e "${YELLOW}----------------------------------------------------${NC}"