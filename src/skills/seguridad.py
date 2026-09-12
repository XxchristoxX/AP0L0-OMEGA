import json
import os
import subprocess
from datetime import datetime
import hashlib
import hmac
import base64
def encrypt_message(message, key):
    return base64.urlsafe_b64encode(hmac.new(key.encode(), message.encode(), hashlib.sha256).digest()).decode()
def decrypt_message(encrypted_message, key):
    return hmac.new(key.encode(), base64.urlsafe_b64decode(encrypted_message.encode()), hashlib.sha256).hexdigest()
def biometric_authentication():
    # Simulación de autenticación biométrica, siempre devuelve True
    return True
def clear_logs():
    log_file = "activity.log"
    if os.path.exists(log_file):
        os.remove(log_file)
def log_activity(action):
    with open("activity.log", "a") as log:
        log.write(f"{datetime.now()}: {action}\n")
def run(params):
    if params.get("mode") == "stealth":
        clear_logs()

    if biometric_authentication():
        if "message" in params and "key" in params:
            encrypted_message = encrypt_message(params["message"], params["key"])
            log_activity(f"Encrypted message sent: {encrypted_message}")
            return {"status": "success", "encrypted_message": encrypted_message}
        else:
            return {"status": "error", "message": "Missing parameters"}
    else:
        return {"status": "error", "message": "Biometric authentication failed"}