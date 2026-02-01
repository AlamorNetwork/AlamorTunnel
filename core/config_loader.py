import json
import os

CONFIG_FILE = "configs/panel_config.json"

def load_config():
    if not os.path.exists("configs"):
        os.makedirs("configs")
    
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