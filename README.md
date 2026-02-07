
# AlamorTunnel 🚀

### Advanced Anti-Censorship Tunneling Panel

![AlamorTunnel Banner](https://raw.githubusercontent.com/Alamor/AlamorTunnel/main/static/img/banner.png)

[![GitHub release](https://img.shields.io/github/v/release/Alamor/AlamorTunnel?style=flat-square)](https://github.com/Alamor/AlamorTunnel/releases)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-yellow?style=flat-square)](https://www.python.org/)

**AlamorTunnel** is a powerful, web-based management panel designed to bypass severe internet censorship. It integrates the most advanced tunneling cores (**Hysteria 2**, **Backhaul**, **Gost**, **Rathole**) into a single, easy-to-use interface.

Features include **Port Hopping**, **Traffic Obfuscation**, **Real-time Speedtest**, and a **Cyberpunk CLI** for server management.

---

## 🌍 Language

- [🇺🇸 English (Default)](#-features)
- [🇮🇷 Persian (فارسی)](README_fa.md)

---

## ✨ Features

* **⚡ Multi-Core Support:**
  * **Hysteria 2:** Built-in **Port Hopping**, Masquerade, and Brutal congestion control.
  * **Backhaul:** Supports TCP, TCPMux, WS, WSS with connection pooling.
  * **Gost:** Chain proxies, forwarding, and multi-protocol support.
  * **Rathole:** Lightweight, secure reverse proxy for NAT traversal.
* **📊 Live Dashboard:**
  * Real-time **Traffic Monitoring** (RX/TX).
  * **Advanced Speedtest:** Check Ping, Download, and Upload speeds directly from the panel.
  * Visual charts for network health.
* **🛡️ Anti-Censorship:**
  * Automatic **Port Hopping** configuration (iptables).
  * Advanced **Masquerade** to mimic real website traffic.
  * **GeoIP Blocking:** Block domestic or specific country IPs (e.g., CN, IR).
* **💻 Cyberpunk CLI:**
  * Professional terminal interface.
  * **One-click SSL:** Auto-configure Nginx & Certbot.
  * Live logs and updates.

## 🚀 Installation

Run the following commands on your **IRAN** server (Ubuntu 20.04+ / Debian 11+ recommended):

```bash
git clone https://github.com/AlamorNetwork/AlamorTunnel.git
cd AlamorTunnel
chmod +x install.sh
./install.sh
```
