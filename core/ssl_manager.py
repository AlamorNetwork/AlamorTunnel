import os
import subprocess

CERT_DIR = "/root/certs"
KEY_FILE = f"{CERT_DIR}/server.key"
CSR_FILE = f"{CERT_DIR}/server.csr"
CRT_FILE = f"{CERT_DIR}/server.crt"

def generate_self_signed_cert(domain_or_ip="127.0.0.1"):
    """
    تولید سرتیفیکیت Self-Signed با OpenSSL برای WSS/WSSMUX
    """
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)

    # اگر فایل‌ها موجود باشند، دوباره نمی‌سازیم تا سرعت بالا برود
    if os.path.exists(CRT_FILE) and os.path.exists(KEY_FILE):
        return True, CRT_FILE, KEY_FILE

    print("[+] Generating OpenSSL Certificates...")

    try:
        # 1. ساخت کلید خصوصی
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-out", KEY_FILE, "-pkeyopt", "rsa_keygen_bits:2048"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 2. ساخت CSR
        subj = f"/C=US/ST=State/L=City/O=Alamor/CN={domain_or_ip}"
        subprocess.run(
            ["openssl", "req", "-new", "-key", KEY_FILE, "-out", CSR_FILE, "-subj", subj],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 3. امضای سرتیفیکیت
        subprocess.run(
            ["openssl", "x509", "-req", "-in", CSR_FILE, "-signkey", KEY_FILE, "-out", CRT_FILE, "-days", "3650"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        return True, CRT_FILE, KEY_FILE

    except Exception as e:
        print(f"[!] SSL Gen Error: {e}")
        return False, str(e), None