import os
import json
from cryptography.fernet import Fernet

class APIKeyManager:
    def __init__(self, vault_path="config/api_vault.enc"):
        self.vault_path = vault_path
        self.key = os.getenv("VAULT_KEY")
        if not self.key:
            self.key = Fernet.generate_key()
            os.environ["VAULT_KEY"] = self.key.decode()
        self.cipher = Fernet(self.key if isinstance(self.key, bytes) else self.key.encode())

    def store_key(self, service, key):
        data = {}
        if os.path.exists(self.vault_path):
            with open(self.vault_path, "rb") as f:
                encrypted = f.read()
                decrypted = self.cipher.decrypt(encrypted)
                data = json.loads(decrypted)
        data[service] = key
        with open(self.vault_path, "wb") as f:
            f.write(self.cipher.encrypt(json.dumps(data).encode()))
        return True

    def get_key(self, service):
        if not os.path.exists(self.vault_path):
            return None
        with open(self.vault_path, "rb") as f:
            encrypted = f.read()
            decrypted = self.cipher.decrypt(encrypted)
            data = json.loads(decrypted)
            return data.get(service)
