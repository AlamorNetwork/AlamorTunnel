import json
import os
import glob

CONFIG_DIR = "configs"

# اطمینان از وجود پوشه کانفیگ
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

def save_tunnel_config(tunnel_data):
    """
    ذخیره اطلاعات تانل در فایل JSON.
    نام فایل ترکیبی از پورت و پروتکل خواهد بود تا یکتا باشد.
    """
    try:
        # tunnel_data باید شامل: id, name, transport, port, token, config (dict) باشد
        filename = f"{CONFIG_DIR}/tunnel_{tunnel_data['transport']}_{tunnel_data['port']}.json"
        
        with open(filename, 'w') as f:
            json.dump(tunnel_data, f, indent=4)
        print(f"[Backup] Config saved: {filename}")
    except Exception as e:
        print(f"[Backup Error] Save failed: {e}")

def delete_tunnel_config(transport, port):
    """حذف فایل کانفیگ"""
    try:
        filename = f"{CONFIG_DIR}/tunnel_{transport}_{port}.json"
        if os.path.exists(filename):
            os.remove(filename)
            print(f"[Backup] Config deleted: {filename}")
    except Exception as e:
        print(f"[Backup Error] Delete failed: {e}")

def load_all_configs():
    """خواندن تمام فایل‌های کانفیگ برای بازیابی دیتابیس"""
    configs = []
    files = glob.glob(f"{CONFIG_DIR}/*.json")
    for file in files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                configs.append(data)
        except Exception as e:
            print(f"[Backup Error] Load failed for {file}: {e}")
    return configs