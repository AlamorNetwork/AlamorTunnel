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

    print("[+] Generating OpenSSL Certificates...")

    try:
        # Step 2: Generate Private Key
        if not os.path.exists(KEY_FILE):
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-out", KEY_FILE, "-pkeyopt", "rsa_keygen_bits:2048"],
                check=True
            )

        # Step 3: Generate CSR (Auto-filling prompts to avoid blocking)
        subj = f"/C=US/ST=State/L=City/O=Alamor/CN={domain_or_ip}"
        subprocess.run(
            ["openssl", "req", "-new", "-key", KEY_FILE, "-out", CSR_FILE, "-subj", subj],
            check=True
        )

        # Step 4: Generate Self-Signed Certificate
        subprocess.run(
            ["openssl", "x509", "-req", "-in", CSR_FILE, "-signkey", KEY_FILE, "-out", CRT_FILE, "-days", "365"],
            check=True
        )
        
        print(f"[+] Certificates generated at {CERT_DIR}")
        return True, CRT_FILE, KEY_FILE

    except subprocess.CalledProcessError as e:
        return False, str(e), None