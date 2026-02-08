

<div align="center">

# 🌌 AlamorTunnel Panel

### The Next-Gen Anti-Censorship Infrastructure

*"Where Restrictions End, Freedom Begins."*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Core-Flask-red?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux-orange?style=for-the-badge&logo=linux)](https://www.linux.org/)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)](https://github.com/AlamorNetwork/AlamorTunnel)

<br>
<img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Rocket.png" alt="Rocket" width="120" />
<br>

<p align="center">
  <b>AlamorTunnel</b> is not just a tool; it's a gateway to the free internet.<br>
  Designed with a stunning <b>Cyberpunk Glassmorphism UI</b>, it simplifies the complexity of advanced tunneling protocols.<br>
  Bypass DPI (Deep Packet Inspection), secure your connection, and reclaim your digital rights.
</p>

[Report Bug](https://github.com/AlamorNetwork/AlamorTunnel/issues) · [Request Feature](https://github.com/AlamorNetwork/AlamorTunnel/issues)

</div>

---

## ⚡ Quick Installation (نصب سریع)

To deploy the full panel on your **Iran Server** (Ubuntu 20.04+ Recommended), run this single command:

```bash
bash <(curl -Ls [https://raw.githubusercontent.com/AlamorNetwork/AlamorTunnel/main/install.sh](https://raw.githubusercontent.com/AlamorNetwork/AlamorTunnel/main/install.sh))
```


> **Note:** This script automatically updates the system, installs dependencies (Python, Nginx, Certbot), and sets up the Systemd service.

---

## 💎 Key Features

| **Feature**             | **Description**                                                                                                         |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **🎨 Modern UI**        | A beautiful, responsive "Glassmorphism" interface designed for ease of use.                                                   |
| **🛡️ Multi-Protocol** | Native support for**Backhaul** , **Hysteria 2** , **Rathole** , **Gost** , and **Slipstream** . |
| **📊 Smart Monitoring** | Real-time charts for Traffic (Upload/Download), CPU, and RAM usage.                                                           |
| **🔐 SSH & Keys**       | Connect to foreign servers securely using**Password**or **SSH Private Keys** .                                    |
| **🚀 Auto-Config**      | Automatically installs and configures the core binaries on the remote server.                                                 |
| **🌍 Domain Manager**   | Built-in SSL certificate generation (Let's Encrypt) and domain management.                                                    |
| **⚡ Speed Test**       | Integrated advanced speed test to measure tunnel latency and throughput.                                                      |

---

## 🛠 Supported Protocols

We support the bleeding edge of anti-censorship technologies:

### 1. Backhaul (Enterprise Grade)

* **Best for:** High throughput, stability, and CDN usage.
* **Features:** TCP, TCP Mux,  **WebSocket (WS)** ,  **WebSocket Secure (WSS)** .
* **Security:** Supports custom SSL certs and token-based auth.

### 2. Hysteria 2 (UDP King)

* **Best for:** Poor network conditions and high packet loss.
* **Features:** Uses a custom QUIC-based protocol to brute-force through restrictions.
* **Note:** Requires UDP ports to be open.

### 3. Rathole (The Lightweight)

* **Best for:** Low-resource servers (Raspberry Pi, Nano VPS).
* **Features:** Written in Rust, extremely fast, secure, and low memory footprint.

### 4. Gost (The Swiss Army Knife)

* **Best for:** Complex routing and forwarding.
* **Features:** Supports almost any protocol combination (HTTP/2, SOCKS5, Relay).

---

## 🖥️ Getting Started

After installation, the panel will start automatically.

1. **Access the Panel:** Open `http://YOUR_IRAN_IP:5050` in your browser.
2. **Login:**
   * **Username:** `admin`
   * **Password:** `admin`
3. **Setup:**
   * Go to **Dashboard** >  **Connect Server** .
   * Enter your Foreign Server IP and Credentials (Password or SSH Key).
   * Navigate to **Tunnels** and deploy your first connection!

> ⚠️ **Security Warning:** Please change your default password immediately from the **Settings** menu.

---

## 📸 Screenshots

<div align="center">

<img src="https://www.google.com/search?q=https://via.placeholder.com/800x400/0f172a/38bdf8%3Ftext%3DAlamor%2BDashboard%2BPreview" alt="Dashboard" style="border-radius: 15px; box-shadow: 0 0 20px rgba(56, 189, 248, 0.5);">

<img src="https://www.google.com/search?q=https://via.placeholder.com/800x400/0f172a/a855f7%3Ftext%3DReal-time%2BTraffic%2BMonitoring" alt="Monitoring" style="border-radius: 15px; box-shadow: 0 0 20px rgba(168, 85, 247, 0.5);">

</div>

---

## 🤝 Contributing

We believe in the power of community. The internet belongs to everyone.

If you have ideas to improve AlamorTunnel, feel free to:

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 Disclaimer

This software is developed for  **educational and research purposes** . The goal is to study network traffic and improve protocol security. The developers are not responsible for any misuse of this tool.

---

<div align="center">

`<sub>`Built with 💻 and ☕ by `<a href="https://www.google.com/search?q=https://github.com/AlamorNetwork">`AlamorNetwork `</a></sub>`

`<sub><i>`"Information wants to be free."`</i></sub>`

</div>

```

### تغییرات و نکات برجسته:

1.  **لینک نصب:** لینک `curl` دقیقاً به `AlamorNetwork` اشاره می‌کند.
2.  **شعار:** "Where Restrictions End, Freedom Begins" (جایی که محدودیت‌ها تمام می‌شوند، آزادی آغاز می‌شود) به عنوان شعار اصلی انتخاب شد.
3.  **بخش‌ها:** توضیحات فنی کاملاً شفاف (Transparent) است تا کاربر بداند دقیقاً چه اتفاقی می‌افتد.
4.  **گرافیک:** از ایموجی‌ها و استایل‌های HTML برای وسط‌چین کردن و زیباسازی استفاده شده است.

کافیست این متن را در فایل `README.md` گیت‌هاب خود پیست (Paste) کنید.
```
