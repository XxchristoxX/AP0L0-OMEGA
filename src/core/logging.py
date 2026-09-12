# core/logging.py
import sys
import logging
from pathlib import Path

def get_logger(name, level=logging.INFO):
    """
    Devuelve un logger configurado con formato simple.
    Si se prefiere logging estándar, se puede usar; si no, devuelve un stub.
    """
    try:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(level)
        return logger
    except Exception:
        class SimpleLogger:
            def info(self, msg): print(f"[{name}] INFO: {msg}")
            def warning(self, msg): print(f"[{name}] WARNING: {msg}")
            def error(self, msg): print(f"[{name}] ERROR: {msg}")
            def debug(self, msg): print(f"[{name}] DEBUG: {msg}")
            def log(self, msg): print(f"[{name}] {msg}")
        return SimpleLogger()