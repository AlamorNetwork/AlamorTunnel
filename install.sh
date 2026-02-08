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

# 2. Update & Install System Dependencies
echo -e "${GREEN}[+] Updating System & Installing Dependencies...${NC}"
# جلوگیری از گیر کردن در پنجره‌های Interactive
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl wget unzip tar iptables-persistent net-tools build-essential

# 3. Setup Project Directory & Clone Repo (THE FIX)
echo -e "${GREEN}[+] Setting up Project Files...${NC}"
INSTALL_DIR="/root/AlamorTunnel"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory exists. Updating repo...${NC}"
    cd $INSTALL_DIR
    git reset --hard
    git pull
else
    echo -e "${CYAN}Cloning repository...${NC}"
    git clone https://github.com/AlamorNetwork/AlamorTunnel.git $INSTALL_DIR
fi

# ایجاد پوشه‌های مورد نیاز اگر در ریپو نباشند
mkdir -p $INSTALL_DIR/bin
mkdir -p $INSTALL_DIR/configs
mkdir -p $INSTALL_DIR/logs
mkdir -p /root/certs
chmod -R 755 $INSTALL_DIR

# 4. Install Python Libraries
echo -e "${GREEN}[+] Installing Python Libraries...${NC}"
pip3 install -r $INSTALL_DIR/requirements.txt --break-system-packages

# 5. Download Cores (Hysteria, Backhaul, Gost, Rathole)
echo -e "${GREEN}[+] Downloading Tunnel Cores...${NC}"
BIN_DIR="$INSTALL_DIR/bin"

# --- Hysteria 2 ---
if [ ! -f "$BIN_DIR/hysteria" ]; then
    echo -e "${CYAN}--> Installing Hysteria 2...${NC}"
    curl -L -k -o $BIN_DIR/hysteria https://github.com/apernet/hysteria/releases/latest/download/hysteria-linux-amd64
    chmod +x $BIN_DIR/hysteria
fi

# --- Backhaul ---
if [ ! -f "$BIN_DIR/backhaul" ]; then
    echo -e "${CYAN}--> Installing Backhaul...${NC}"
    curl -L -k -o $BIN_DIR/backhaul.tar.gz https://github.com/Musixal/Backhaul/releases/latest/download/backhaul_linux_amd64.tar.gz
    tar -xzf $BIN_DIR/backhaul.tar.gz -C $BIN_DIR
    mv $BIN_DIR/backhaul_linux_amd64 $BIN_DIR/backhaul 2>/dev/null || true
    chmod +x $BIN_DIR/backhaul
    rm $BIN_DIR/backhaul.tar.gz
fi

# --- Gost ---
if [ ! -f "$BIN_DIR/gost" ]; then
    echo -e "${CYAN}--> Installing Gost...${NC}"
    curl -L -k -o $BIN_DIR/gost.gz https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz
    gzip -d -f $BIN_DIR/gost.gz
    chmod +x $BIN_DIR/gost
fi

# --- Rathole ---
if [ ! -f "$BIN_DIR/rathole" ]; then
    echo -e "${CYAN}--> Installing Rathole...${NC}"
    curl -L -k -o $BIN_DIR/rathole.zip https://github.com/rapiz1/rathole/releases/latest/download/rathole-x86_64-unknown-linux-gnu.zip
    unzip -o $BIN_DIR/rathole.zip -d $BIN_DIR
    chmod +x $BIN_DIR/rathole
    rm $BIN_DIR/rathole.zip
fi

# 6. Initialize Database
echo -e "${GREEN}[+] Initializing Database...${NC}"
cd $INSTALL_DIR
# حالا که فایل‌ها کلون شده‌اند، این دستور کار می‌کند
python3 -c "from core.database import init_db; init_db(); print('Database initialized successfully.')"

# 7. Create Service
echo -e "${GREEN}[+] Creating Systemd Service...${NC}"
cat > /etc/systemd/system/alamor.service <<EOL
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

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
CLI_SCRIPT="$INSTALL_DIR/alamor_cli.py"
if [ -f "$CLI_SCRIPT" ]; then
    chmod +x $CLI_SCRIPT
    ln -sf $CLI_SCRIPT /usr/bin/alamor
    echo -e "${CYAN}CLI installed successfully.${NC}"
else
    echo -e "${RED}Warning: alamor_cli.py not found!${NC}"
fi

echo -e "${YELLOW}----------------------------------------------------${NC}"
echo -e "${GREEN} INSTALLATION COMPLETE! ${NC}"
echo -e "${CYAN} Panel is running on port 5050 ${NC}"
echo -e "${CYAN} Type 'alamor' to open the CLI menu. ${NC}"
echo -e "${YELLOW}----------------------------------------------------${NC}"