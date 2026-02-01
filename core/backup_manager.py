import json
import os
import glob

CONFIG_DIR = "configs"

if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

def save_tunnel_config(tunnel_data):
    """ذخیره تانل در فایل برای ماندگاری بدون دیتابیس"""
    try:
        # نام فایل: tunnel_transport_port.json
        filename = f"{CONFIG_DIR}/tunnel_{tunnel_data['transport']}_{tunnel_data['port']}.json"
        
        # تبدیل Row به دیکشنری معمولی اگر لازم باشد
        data_to_save = dict(tunnel_data) if not isinstance(tunnel_data, dict) else tunnel_data
        
        # اگر فیلد کانفیگ رشته است، تبدیل به دیکشنری شود (برای خوانایی فایل)
        if isinstance(data_to_save.get('config'), str):
            try:
                data_to_save['config'] = json.loads(data_to_save['config'])
            except:
                pass

        with open(filename, 'w') as f:
            json.dump(data_to_save, f, indent=4)
    except Exception as e:
        print(f"Backup Error: {e}")

def delete_tunnel_config(transport, port):
    try:
        filename = f"{CONFIG_DIR}/tunnel_{transport}_{port}.json"
        if os.path.exists(filename):
            os.remove(filename)
    except:
        pass

def load_all_configs():
    """بازیابی کل تانل‌ها از فایل"""
    configs = []
    files = glob.glob(f"{CONFIG_DIR}/*.json")
    for file in files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                # در دیتابیس، کانفیگ باید رشته باشد
                if isinstance(data.get('config'), dict):
                     data['config'] = json.dumps(data['config'])
                configs.append(data)
        except:
            pass
    return configs