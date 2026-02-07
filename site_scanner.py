import socket
import ssl
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# لیست دامنه‌های پیشنهادی (سایت‌های پربازدید ایرانی)
# می‌توانید دامنه‌های دیگر را هم به این لیست اضافه کنید
CANDIDATES = [
    "www.digikala.com",
    "www.aparat.com",
    "www.varzesh3.com",
    "www.filimo.com",
    "www.namava.ir",
    "www.telewebion.com",
    "divar.ir",
    "snapp.ir",
    "torob.com",
    "bama.ir",
    "www.shatelland.com",
    "www.asiatech.ir",
    "www.mci.ir",
    "www.irancel.ir",
    "cafebazaar.ir",
    "tamasha.com",
    "www.blogfa.com",
    "www.ninisite.com"
]

def check_sni(domain):
    """
    بررسی قابلیت اتصال، TLS و سرعت دامنه از سرور خارج
    """
    results = {
        "domain": domain,
        "valid": False,
        "tls_version": None,
        "latency": 0,
        "status_code": 0,
        "msg": ""
    }
    
    # تمیز کردن دامنه
    clean_domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    
    try:
        # 1. تست اتصال TCP و اندازه‌گیری پینگ
        start_time = time.time()
        context = ssl.create_default_context()
        
        with socket.create_connection((clean_domain, 443), timeout=5) as sock:
            # 2. تست هندشیک TLS (مهم برای SNI)
            with context.wrap_socket(sock, server_hostname=clean_domain) as ssock:
                results["tls_version"] = ssock.version()
        
        latency = (time.time() - start_time) * 1000 # میلی‌ثانیه
        results["latency"] = round(latency, 2)
        
        # 3. تست HTTP Response (برای اطمینان از باز بودن سایت)
        try:
            r = requests.get(f"https://{clean_domain}", timeout=5, allow_redirects=True)
            results["status_code"] = r.status_code
            if 200 <= r.status_code < 400:
                results["valid"] = True
                results["msg"] = "OK"
            else:
                results["msg"] = f"Bad Status: {r.status_code}"
        except Exception as e:
            results["msg"] = "HTTP Error (Site might block external IPs)"
            
    except socket.timeout:
        results["msg"] = "Timeout (Blocked?)"
    except ssl.SSLError:
        results["msg"] = "SSL Error (No TLS support?)"
    except socket.gaierror:
        results["msg"] = "DNS Error (Invalid Domain)"
    except Exception as e:
        results["msg"] = str(e)
        
    return results

def main():
    print(f"{'DOMAIN':<25} | {'STATUS':<10} | {'PING (ms)':<10} | {'TLS':<10} | {'NOTE'}")
    print("-" * 80)
    
    # اجرای همزمان برای سرعت بیشتر
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_sni, domain): domain for domain in CANDIDATES}
        
        valid_snis = []
        
        for future in futures:
            res = future.result()
            status_icon = "✅" if res["valid"] else "❌"
            print(f"{res['domain']:<25} | {status_icon} {res['status_code']:<6} | {res['latency']:<10} | {res['tls_version'] or 'N/A':<10} | {res['msg']}")
            
            if res["valid"]:
                valid_snis.append(res)

    print("-" * 80)
    print("\n[+] Recommended Candidates for SNI:")
    # مرتب‌سازی بر اساس کمترین پینگ
    valid_snis.sort(key=lambda x: x["latency"])
    for item in valid_snis:
        print(f"   -> {item['domain']} (Ping: {item['latency']}ms)")

if __name__ == "__main__":
    main()