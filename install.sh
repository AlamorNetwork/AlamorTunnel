#!/bin/bash

# ==========================================
# ALAMOR TUNNEL INSTALLER - OFFLINE PACK
# ==========================================

# --- CONFIGURATION ---
# آی‌پی سرور دانلود خودت را اینجا وارد کن
REPO_URL="https://files.irplatforme.ir/files"
INSTALL_DIR="/root/AlamorTunnel"
BIN_DIR="$INSTALL_DIR/bin"

# رنگ‌ها
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}[!] Please run as root.${NC}"
  exit 1
fi

clear
echo -e "${CYAN}>>> Initializing Alamor Panel Deployment...${NC}"
sleep 1

# 1. نصب پکیج‌های سیستم
echo -e "\n${CYAN}[1/5] Installing System Dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-dev build-essential libssl-dev libffi-dev \
    git curl wget nano tar unzip nginx certbot python3-certbot-nginx net-tools ufw
echo -e "${GREEN}✔ Dependencies Installed${NC}"

# 2. آماده‌سازی پوشه‌ها
echo -e "\n${CYAN}[2/5] Setting up Directories...${NC}"
mkdir -p "$BIN_DIR"
mkdir -p "$INSTALL_DIR/configs"
mkdir -p "$INSTALL_DIR/certs"
mkdir -p "$INSTALL_DIR/core"

# 3. دانلود هسته‌های تانل (Core Binaries)
echo -e "\n${CYAN}[3/5] Downloading Tunnel Cores from Private Repo...${NC}"

download_core() {
    NAME=$1
    echo -ne "  ➜ Downloading ${YELLOW}$NAME${NC} ... "
    wget -q -O "$BIN_DIR/$NAME.tar.gz" "$REPO_URL/$NAME.tar.gz"
    
    if [ $? -eq 0 ]; then
        # اکسترکت کردن
        tar -xzf "$BIN_DIR/$NAME.tar.gz" -C "$BIN_DIR"
        chmod +x "$BIN_DIR/$NAME"
        rm "$BIN_DIR/$NAME.tar.gz"
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED!${NC} (Check Repo URL)"
    fi
}

download_core "backhaul"
download_core "gost"
download_core "hysteria"
download_core "rathole"

# اضافه کردن مسیر bin به PATH سیستم برای دسترسی راحت‌تر
if ! grep -q "$BIN_DIR" ~/.bashrc; then
    echo "export PATH=\$PATH:$BIN_DIR" >> ~/.bashrc
    export PATH=$PATH:$BIN_DIR
fi

# 4. نصب کتابخانه‌های پایتون
echo -e "\n${CYAN}[4/5] Installing Python Libraries...${NC}"
pip3 install --upgrade pip
# نصب مستقیم پیشنیازها
pip3 install Flask requests paramiko werkzeug gunicorn psutil speedtest-cli pyOpenSSL cryptography cffi dnspython
echo -e "${GREEN}✔ Python Environment Ready${NC}"

# 5. ساخت سرویس و اجرا
echo -e "\n${CYAN}[5/5] Finalizing Setup...${NC}"

# کپی فایل‌های پروژه (فرض بر این است که فایل‌ها در پوشه جاری هستند)
# اگر فایل اینستالر کنار فایل‌های پروژه است، نیازی به کپی نیست

# ساخت سرویس
cat > /etc/systemd/system/alamor.service <<EOF
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 0.0.0.0:5050 app:app
Environment="PATH=$PATH:$BIN_DIR"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable alamor
systemctl restart alamor

SERVER_IP=$(curl -s ifconfig.me)
echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}   INSTALLATION COMPLETE - CORES LOADED${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Repo Source  :${NC} $REPO_URL"
echo -e "${YELLOW}Access Panel :${NC} http://${SERVER_IP}:5050"
echo -e "${GREEN}====================================================${NC}"