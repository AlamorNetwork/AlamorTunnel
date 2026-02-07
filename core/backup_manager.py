import json
import os

# مسیر ذخیره فایل‌های جیسون
CONFIGS_DIR = '/root/AlamorTunnel/configs'

def ensure_configs_dir():
    if not os.path.exists(CONFIGS_DIR):
        os.makedirs(CONFIGS_DIR)

def save_tunnel_config(tunnel_id, config_data):
    """
    ذخیره کانفیگ تانل در فایل JSON
    """
    ensure_configs_dir()
    file_path = os.path.join(CONFIGS_DIR, f"tunnel_{tunnel_id}.json")
    try:
        with open(file_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving backup for tunnel {tunnel_id}: {e}")
        return False

def delete_tunnel_config(tunnel_id):
    """
    حذف فایل کانفیگ تانل
    """
    file_path = os.path.join(CONFIGS_DIR, f"tunnel_{tunnel_id}.json")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"Error deleting backup for tunnel {tunnel_id}: {e}")
            return False
    return False

def load_all_configs():
    """
    لود کردن تمام کانفیگ‌ها برای بازگردانی دیتابیس
    """
    ensure_configs_dir()
    configs = []
    if not os.path.exists(CONFIGS_DIR):
        return configs

    for filename in os.listdir(CONFIGS_DIR):
        if filename.endswith(".json") and filename.startswith("tunnel_"):
            file_path = os.path.join(CONFIGS_DIR, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    configs.append(data)
            except Exception as e:
                print(f"Error loading backup {filename}: {e}")
    return configs

def restore_database_from_backup():
    """
    بازگردانی دیتابیس از روی فایل‌های جیسون
    """
    # ایمپورت را اینجا انجام می‌دهیم تا چرخه ایمپورت شکسته شود
    from core.database import Database
    
    db = Database()
    configs = load_all_configs()
    
    restored_count = 0
    for config in configs:
        # بررسی اینکه آیا تانل قبلاً وجود دارد یا نه
        existing = db.get_tunnel(config.get('id'))
        if not existing:
            try:
                # اضافه کردن تانل به دیتابیس
                # نکته: پارامترها باید طبق ساختار جدول شما باشد
                # فرض بر این است که دیکشنری config کلیدهای مناسب را دارد
                db.add_tunnel(
                    server_ip=config.get('remote_ip'),
                    server_port=config.get('remote_port'),
                    local_port=config.get('local_port'),
                    protocol=config.get('protocol'),
                    ssh_user=config.get('ssh_user'),
                    ssh_pass=config.get('ssh_pass'),
                    # سایر فیلدها...
                )
                restored_count += 1
            except Exception as e:
                print(f"Failed to restore tunnel {config.get('id')}: {e}")
                
    return restored_count