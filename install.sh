#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}
    _    _                                _____                      _ 
   / \  | | __ _ _ __ ___   ___  _ __    |_   _|   _ _ __  _ __   ___| |
  / _ \ | |/ _\` | '_ \` _ \ / _ \| '__|     | || | | | '_ \| '_ \ / _ \ |
 / ___ \| | (_| | | | | | | (_) | |        | || |_| | | | | | | |  __/ |
/_/   \_\_|\__,_|_| |_| |_|\___/|_|        |_| \__,_|_| |_|_| |_|\___|_|
                                                                        
${NC}"
echo -e "${YELLOW}>>> Starting AlamorTunnel Installation on IRAN Server...${NC}"

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
echo -e "${GREEN}[+] Creating Directories...${NC}"
mkdir -p /root/AlamorTunnel/bin
mkdir -p /root/AlamorTunnel/configs
mkdir -p /root/certs
chmod 755 /root/AlamorTunnel/bin

# 4. Install Python Libs
echo -e "${GREEN}[+] Installing Python Libraries...${NC}"
pip3 install -r /root/AlamorTunnel/requirements.txt --break-system-packages

# 5. Download Cores (Hysteria, Backhaul, Gost, Rathole)
echo -e "${GREEN}[+] Downloading Tunnel Cores...${NC}"
BIN_DIR="/root/AlamorTunnel/bin"

# --- Hysteria 2 ---
echo -e "${CYAN}--> Installing Hysteria 2...${NC}"
curl -L -o $BIN_DIR/hysteria https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64
chmod +x $BIN_DIR/hysteria

# --- Backhaul ---
echo -e "${CYAN}--> Installing Backhaul...${NC}"
curl -L -o $BIN_DIR/backhaul.tar.gz https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz
tar -xzf $BIN_DIR/backhaul.tar.gz -C $BIN_DIR
mv $BIN_DIR/backhaul_linux_amd64 $BIN_DIR/backhaul 2>/dev/null || true # Fix naming if needed
chmod +x $BIN_DIR/backhaul
rm $BIN_DIR/backhaul.tar.gz

# --- Gost ---
echo -e "${CYAN}--> Installing Gost...${NC}"
curl -L -o $BIN_DIR/gost.gz https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz
gzip -d -f $BIN_DIR/gost.gz
chmod +x $BIN_DIR/gost

# --- Rathole ---
echo -e "${CYAN}--> Installing Rathole...${NC}"
curl -L -o $BIN_DIR/rathole.zip https://github.com/rapiz1/rathole/releases/latest/download/rathole-x86_64-unknown-linux-gnu.zip
unzip -o $BIN_DIR/rathole.zip -d $BIN_DIR
chmod +x $BIN_DIR/rathole
rm $BIN_DIR/rathole.zip

# 6. Initialize Database
echo -e "${GREEN}[+] Initializing Database...${NC}"
cd /root/AlamorTunnel
python3 -c "from core.database import init_db; init_db(); print('Database initialized successfully.')"

# 7. Create Service
echo -e "${GREEN}[+] Creating Systemd Service...${NC}"
cat > /etc/systemd/system/alamor.service <<EOL
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=/root/AlamorTunnel
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOL

# 8. Start Services
echo -e "${GREEN}[+] Starting Services...${NC}"
systemctl daemon-reload
systemctl enable alamor
systemctl restart alamor

# 9. CLI Setup
echo -e "${GREEN}[+] Setting up CLI...${NC}"
chmod +x /root/AlamorTunnel/alamor_cli.py
ln -sf /root/AlamorTunnel/alamor_cli.py /usr/bin/alamor

echo -e "${YELLOW}----------------------------------------------------${NC}"
echo -e "${GREEN} INSTALLATION COMPLETE! ${NC}"
echo -e "${CYAN} Panel is running on port 5050 ${NC}"
echo -e "${CYAN} Type 'alamor' to open the CLI menu. ${NC}"
echo -e "${YELLOW}----------------------------------------------------${NC}"