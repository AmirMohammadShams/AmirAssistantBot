import json
import os
import logging
from config import config

logger = logging.getLogger(__name__)
ADMINS_FILE = 'admins.json'

def _load_admins():
    if not os.path.exists(ADMINS_FILE):
        return []
    try:
        with open(ADMINS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading admins: {e}")
        return []

def _save_admins(admins):
    try:
        with open(ADMINS_FILE, 'w') as f:
            json.dump(admins, f)
    except Exception as e:
        logger.error(f"Error saving admins: {e}")

def get_all_admins():
    admins = _load_admins()
    super_admin = str(config.TELEGRAM_CHAT_ID)
    if super_admin and super_admin not in admins:
        admins.append(super_admin)
    return admins

def is_admin(chat_id):
    return str(chat_id) in get_all_admins()

def add_admin(chat_id):
    chat_id = str(chat_id)
    admins = _load_admins()
    if chat_id not in admins:
        admins.append(chat_id)
        _save_admins(admins)
        return True
    return False

def remove_admin(chat_id):
    chat_id = str(chat_id)
    admins = _load_admins()
    if chat_id in admins:
        admins.remove(chat_id)
        _save_admins(admins)
        return True
    return False
