import json
from pathlib import Path

CONFIG_PATH = Path("src/config/api_keys.json")

class PersonalityManager:
    @staticmethod
    def get_current_personality() -> str:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("personality", "apolo")
        except Exception:
            return "apolo"

    @staticmethod
    def get_voice() -> str:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("voice", "Fenrir")
        except Exception:
            return "Fenrir"
