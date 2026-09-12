# src/config/settings.py
from pathlib import Path
import sys

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "src" / "config"
API_CONFIG_PATH = CONFIG_DIR / "api_keys.json"
API_FILE = API_CONFIG_PATH
PROMPT_PATH = BASE_DIR / "src" / "core" / "prompt.txt"

LIVE_MODEL = "gemini-2.0-flash-exp"
LITE_MODEL = "gemini-2.0-flash-exp"
AUDIO_MODEL = "gemini-2.0-flash-exp"

CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

DEFAULT_W, DEFAULT_H = 1020, 740
MIN_W, MIN_H = 860, 620
LEFT_W = 280
RIGHT_W = 350
FLOAT_W, FLOAT_H = 380, 180

DEFAULT_THEME = "#00ff88"
AUTO_LEARN_INTERVAL = 600
ENABLE_ADMIN_CHECK = False
