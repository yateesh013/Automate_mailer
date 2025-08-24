from cryptography.fernet import Fernet
import os, json

CONFIG_FILE = "config.secure"
KEY_FILE = "secret.key"

# Generate key (only once)
def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)

def load_key():
    with open(KEY_FILE, "rb") as f:
        return f.read()

def save_credentials(data: dict):
    generate_key()
    key = load_key()
    fernet = Fernet(key)

    encrypted = fernet.encrypt(json.dumps(data).encode())
    with open(CONFIG_FILE, "wb") as f:
        f.write(encrypted)

def load_credentials():
    if not os.path.exists(CONFIG_FILE):
        return None
    key = load_key()
    fernet = Fernet(key)

    with open(CONFIG_FILE, "rb") as f:
        encrypted = f.read()
    try:
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())
    except Exception:
        return None


if __name__ == "__main__":
    # Example usage

    creds = load_credentials()
    print(creds)
