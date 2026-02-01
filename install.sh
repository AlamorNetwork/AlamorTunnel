#!/bin/bash

# ==========================================
# ALAMOR TUNNEL INSTALLER - ULTIMATE EDITION
# ==========================================

# رنگ‌های نئونی برای خروجی جذاب
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# چک کردن دسترسی روت
if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}[!] Please run as root.${NC}"
  exit 1
fi

clear
echo -e "${CYAN}"
echo "    _    _                                  "
echo "   / \  | | __ _ _ __ ___   ___  _ __     "
echo "  / _ \ | |/ _\` | '_ \` _ \ / _ \| '__|    "
echo " / ___ \| | (_| | | | | | | (_) | |       "
echo "/_/   \_\_|\__,_|_| |_| |_|\___/|_|       "
echo -e "${NC}"
echo -e "${YELLOW}>>> Initializing System Deployment...${NC}"
sleep 2

# تابع مدیریت خطا
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✔ Success${NC}"
    else
        echo -e "${RED}✖ Failed! Error occurred in previous step.${NC}"
        exit 1
    fi
}

# 1. آپدیت سیستم و نصب ابزارهای پایه
echo -e "\n${CYAN}[1/6] Updating Repositories & Installing Dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-dev build-essential libssl-dev libffi-dev \
    git curl wget nano tar unzip nginx certbot python3-certbot-nginx net-tools
check_status

# 2. رفع تداخل‌های احتمالی OpenSSL (حیاتی برای Certbot)
echo -e "\n${CYAN}[2/6] Fixing SSL Library Conflicts...${NC}"
echo "Removing conflicting system packages..."
apt-get remove -y python3-openssl python3-cryptography 2>/dev/null
echo "Done."

# 3. نصب کتابخانه‌های پایتون
echo -e "\n${CYAN}[3/6] Installing Python Environment...${NC}"
# ارتقای pip
pip3 install --upgrade pip
# نصب پیشنیازها
pip3 install -r requirements.txt
# فورس آپدیت کتابخانه‌های رمزنگاری
pip3 install --upgrade pyOpenSSL cryptography cffi certbot
check_status

# 4. آماده‌سازی فایل‌ها و پوشه‌ها
echo -e "\n${CYAN}[4/6] Configuring File Structure...${NC}"
mkdir -p configs
mkdir -p certs
mkdir -p core
chmod +x install.sh uninstall.sh
echo "Permissions set."

# 5. ساخت سرویس Systemd
echo -e "\n${CYAN}[5/6] Creating System Service (alamor.service)...${NC}"
cat > /etc/systemd/system/alamor.service <<EOF
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 0.0.0.0:5050 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
check_status

# 6. راه‌اندازی نهایی
echo -e "\n${CYAN}[6/6] Launching Panel...${NC}"
systemctl enable alamor
systemctl restart alamor
check_status

# دریافت IP سرور
SERVER_IP=$(curl -s ifconfig.me)

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}   INSTALLATION COMPLETE - SYSTEM ONLINE${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Access Panel :${NC} http://${SERVER_IP}:5050"
echo -e "${YELLOW}Default User :${NC} admin"
echo -e "${YELLOW}Default Pass :${NC} admin"
echo -e "${CYAN}----------------------------------------------------${NC}"
echo -e "Logs command : journalctl -u alamor -f"
echo -e "${GREEN}====================================================${NC}"