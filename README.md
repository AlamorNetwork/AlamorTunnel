# 🐍 AlamorTunnel Enterprise

![Version](https://img.shields.io/badge/version-2.0.0-succes)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Ubuntu-orange?logo=linux&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

> **The Ultimate Tunneling Infrastructure Orchestrator.** > Manage your local and remote servers, tunnels, and network optimizations from a single, glass-morphism dashboard.

---

## 🌟 Features (قابلیت‌ها)

AlamorTunnel is not just a script; it's a full-stack infrastructure manager designed for stability and stealth.

### 🔥 Core Capabilities

* **Orchestration Mode:** Manage remote ("Slave") servers from a central ("Master") Iran server securely via SSH keys.
* **Smart Installer:** Auto-detects network issues and switches Python mirrors automatically (Anti-Filter).
* **Sequential Logic:** Prevents server overload by queuing tasks (Install BBR -> Config Tunnel -> Update DNS).
* **Clean IP Injection:** Integrated scanner to find clean Cloudflare IPs and inject them into X-UI configs instantly.

### 🎨 UI & UX

* **Slytherin Prime Theme:** A modern, dark-mode "Glassmorphism" interface with neon green accents.
* **Real-time Dashboard:** Monitor CPU, RAM, and Connection Health (Ping/Packet Loss) visually.
* **Responsive Design:** Fully compatible with Desktop and Mobile browsers.

### 🛠 Tools & Tunnels

* **Tunnel Support:**
  * 🚀 **Backhaul:** TCP-optimized reverse tunnel (Great for gaming).
  * 🛡️ **Rathole:** Secure, Rust-based tunnel for high-restriction environments.
  * 👻 **ICMP/DNS:** Stealth tunneling methods.
* **System Opt:** One-click BBR, Cube, and Firewall management.

---

## 📸 Screenshots

|                                       Login Screen                                       |                                     Dashboard Overview                                     |
| :---------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------: |
| ![Login](https://via.placeholder.com/400x250/000000/10b981?text=Login+Page+Slytherin+Style) | ![Dashboard](https://via.placeholder.com/400x250/0f0f0f/10b981?text=Glassmorphism+Dashboard) |

*(Screenshots will be updated soon)*

---

## 🚀 Installation (نصب سریع)

Run this command on your **Iran Server (Master Node)**. The script handles everything automatically.

```bash
apt update -y && apt install git -y && git clone https://github.com/AlamorNetwork/AlamorTunnel.git && cd AlamorTunnel && chmod +x install.sh && ./install.sh
```
