#!/bin/bash

# رنگ‌ها
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN}    ALAMOR TUNNEL ENTERPRISE INSTALLER v2.0     ${NC}"
echo -e "${CYAN}====================================================${NC}"

# 1. بررسی دسترسی روت
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Please run as root.${NC}"
  exit 1
fi

# 2. آپدیت سیستم و نصب پیش‌نیازهای سیستمی
echo -e "${YELLOW}[+] Updating System repositories...${NC}"
apt-get update -qq
echo -e "${YELLOW}[+] Installing System Dependencies...${NC}"
apt-get install -y python3 python3-pip python3-venv git curl wget nano -qq

# 3. نصب کتابخانه‌های پایتون با قابلیت چرخش میرور (Failover)
echo -e "${YELLOW}[+] Installing Python Libraries with Mirror Fallback...${NC}"

MIRRORS=(
    "https://pypi.tuna.tsinghua.edu.cn/simple"
    "https://files.pythonhosted.org/packages"
    "https://pypi.org/simple"
)

INSTALLED=false

for MIRROR in "${MIRRORS[@]}"; do
    echo -e "${CYAN}[~] Trying mirror: $MIRROR${NC}"
    pip3 install -r requirements.txt --ignore-installed -i "$MIRROR" --timeout 30
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[OK] Successfully installed libraries from $MIRROR${NC}"
        INSTALLED=true
        break
    else
        echo -e "${RED}[X] Failed to install from $MIRROR. Trying next...${NC}"
    fi
done

if [ "$INSTALLED" = false ]; then
    echo -e "${RED}[!] Critical Error: Could not install Python libraries from any mirror.${NC}"
    exit 1
fi

# 4. تنظیم سرویس Systemd
echo -e "${YELLOW}[+] Configuring Service...${NC}"
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

[Install]
WantedBy=multi-user.target
EOF

# 5. ساخت دستور CLI (alamor)
echo -e "${YELLOW}[+] Creating 'alamor' CLI command...${NC}"
cat > /usr/bin/alamor <<EOF
#!/bin/bash
cd $(pwd)
python3 alamor_cli.py
EOF
chmod +x /usr/bin/alamor

# 6. راه‌اندازی نهایی
systemctl daemon-reload
systemctl enable alamor
systemctl restart alamor

# 7. ساخت دیتابیس اولیه
python3 -c "from core.database import init_db, create_initial_user; init_db(); create_initial_user()"

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN} INSTALLATION COMPLETE!                             ${NC}"
echo -e "${CYAN} Web Panel: http://$(curl -s ifconfig.me):5050      ${NC}"
echo -e "${CYAN} CLI Menu:  Type 'alamor' in terminal               ${NC}"
echo -e "${GREEN}====================================================${NC}"