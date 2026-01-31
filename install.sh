#!/bin/bash
# AlamorTunnel/install.sh

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}    ALAMOR TUNNEL ENTERPRISE INSTALLER v2.1     ${NC}"
echo -e "${CYAN}====================================================${NC}"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run as root.${NC}"
  exit 1
fi

echo -e "${YELLOW}[+] Updating System & Dependencies...${NC}"
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv git curl wget nano unzip -qq

# Installing Python Libs
echo -e "${YELLOW}[+] Installing Python Libraries...${NC}"
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

# Service Config
echo -e "${YELLOW}[+] Configuring Systemd Service...${NC}"
cat > /etc/systemd/system/alamor.service <<EOF
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/app.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# CLI Command
echo -e "${YELLOW}[+] Creating 'alamor' CLI tool...${NC}"
cat > /usr/bin/alamor <<EOF
#!/bin/bash
cd $(pwd)
python3 alamor_cli.py
EOF
chmod +x /usr/bin/alamor

# Start Service
systemctl daemon-reload
systemctl enable alamor
systemctl restart alamor

# Init DB
echo -e "${YELLOW}[+] Initializing Database...${NC}"
python3 -c "from core.database import init_db; init_db()"

# Final Output
HOST_IP=$(curl -s ifconfig.me)
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN} INSTALLATION COMPLETE!                             ${NC}"
echo -e "${CYAN} Web Panel: http://$HOST_IP:5050                    ${NC}"
echo -e "${CYAN} Username:  admin                                   ${NC}"
echo -e "${CYAN} Password:  admin                                   ${NC}"
echo -e "${CYAN} CLI Menu:  Type 'alamor'                           ${NC}"
echo -e "${GREEN}====================================================${NC}"