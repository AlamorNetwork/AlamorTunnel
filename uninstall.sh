#!/bin/bash

# رنگ‌ها
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}   UNINSTALLING ALAMOR TUNNEL PANEL     ${NC}"
echo -e "${RED}========================================${NC}"
read -p "Are you sure? This will delete all data! (y/n): " confirm

if [[ $confirm == "y" || $confirm == "Y" ]]; then
    echo -e "${RED}[-] Stopping Service...${NC}"
    systemctl stop alamor
    systemctl disable alamor

    echo -e "${RED}[-] Removing Systemd Service...${NC}"
    rm /etc/systemd/system/alamor.service
    systemctl daemon-reload

    echo -e "${RED}[-] Removing CLI Command...${NC}"
    rm /usr/bin/alamor

    echo -e "${RED}[-] Deleting Project Files...${NC}"
    # خارج شدن از پوشه قبل از حذف
    cd ..
    rm -rf AlamorTunnel

    echo -e "${GREEN}[OK] Uninstallation Complete.${NC}"
else
    echo -e "${GREEN}Cancelled.${NC}"
fi