#!/bin/bash

# رنگ‌ها
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}   Installing AlamorTunnel Panel    ${NC}"
echo -e "${GREEN}====================================${NC}"

# 1. آپدیت سیستم
apt-get update

# 2. نصب پایتون و ابزارها
apt-get install -y python3 python3-pip python3-venv

# 3. نصب کتابخانه‌ها
pip3 install -r requirements.txt

# 4. ایجاد سرویس systemd برای اجرای دائم
cat > /etc/systemd/system/alamor.service <<EOF
[Unit]
Description=AlamorTunnel Panel
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/app.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 5. فعال‌سازی سرویس
systemctl daemon-reload
systemctl enable alamor
systemctl start alamor

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN} Installation Finished!             ${NC}"
echo -e "${GREEN} Panel is running on port 5050      ${NC}"
echo -e "${GREEN}====================================${NC}"

# اجرای دستی برای نمایش پسورد بار اول
python3 -c "from core.database import init_db, create_initial_user; init_db(); create_initial_user()"