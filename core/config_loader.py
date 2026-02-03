import json
import os
import sys

# پیدا کردن مسیرِ پوشه‌ای که فایل app.py در آن اجرا شده است (مسیر داینامیک)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "configs")
CONFIG_FILE = os.path.join(CONFIG_DIR, "panel_config.json")

def load_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    
    if not os.path.exists(CONFIG_FILE):
        return {}
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_config(key, value):
    config = load_config()
    config[key] = value
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    return config