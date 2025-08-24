import os
from typing import Optional, Tuple
import requests
from flask import current_app

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
KEY_FILE = os.path.join(DATA_DIR, 'openai_api_key.txt')

OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')


def get_openai_key() -> Optional[str]:
    key = current_app.config.get('OPENAI_API_KEY')
    if key:
        return key
    # Try file
    try:
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'r', encoding='utf-8') as f:
                key = f.read().strip()
                if key:
                    current_app.config['OPENAI_API_KEY'] = key
                    return key
    except Exception:
        pass
    # Fallback to env
    env_key = os.getenv('OPENAI_API_KEY', '').strip()
    if env_key:
        current_app.config['OPENAI_API_KEY'] = env_key
        return env_key
    return None


def set_openai_key(key: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        f.write(key.strip())
    current_app.config['OPENAI_API_KEY'] = key.strip()


def validate_openai_key(key: str) -> Tuple[bool, str]:
    """Validate key by calling a lightweight endpoint. Returns (ok, message)."""
    key = (key or '').strip()
    if not key or not key.startswith('sk-'):
        return False, 'Key format looks invalid.'
    try:
        r = requests.get(
            f"{OPENAI_API_BASE}/models",
            headers={
                'Authorization': f'Bearer {key}'
            },
            timeout=15
        )
        if r.status_code == 200:
            return True, 'OK'
        else:
            try:
                data = r.json()
                msg = data.get('error', {}).get('message') or r.text
            except Exception:
                msg = r.text
            return False, msg
    except requests.RequestException as e:
        return False, str(e)