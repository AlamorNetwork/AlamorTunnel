#!/bin/bash
# AlamorTunnel/uninstall.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}!!! WARNING !!!${NC}"
echo -e "This will completely remove AlamorTunnel and all configurations."
read -p "Are you sure? (y/n): " confirm

if [[ $confirm == "y" || $confirm == "Y" ]]; then
    echo -e "${RED}[-] Stopping Services...${NC}"
    systemctl stop alamor
    systemctl disable alamor
    
    # Stop tunnels
    systemctl stop hysteria-server hysteria-client 2>/dev/null
    systemctl stop backhaul 2>/dev/null
    
    echo -e "${RED}[-] Removing Files...${NC}"
    rm /etc/systemd/system/alamor.service
    rm /usr/bin/alamor
    systemctl daemon-reload
    
    # Remove Project Dir (Current dir's parent usually, handled manually to be safe)
    # We only remove service files. User should delete folder manually if needed to avoid accidents.
    
    echo -e "${GREEN}[OK] Uninstall finished. You can now remove the directory.${NC}"
else
    echo -e "Cancelled."
fi