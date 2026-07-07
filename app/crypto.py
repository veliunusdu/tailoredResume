import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Retrieve the master key from environment variables
MASTER_KEY = os.getenv("ENCRYPTION_MASTER_KEY")

if not MASTER_KEY:
    # In a real production app, we would fail loudly here.
    # For initial setup, we provide a warning.
    print("WARNING: ENCRYPTION_MASTER_KEY not found in environment. Encryption will fail.")

def get_fernet() -> Fernet:
    if not MASTER_KEY:
        raise ValueError("ENCRYPTION_MASTER_KEY is missing from .env")
    return Fernet(MASTER_KEY.encode())

def encrypt_value(value: str) -> str:
    """Encrypt a plain text string."""
    if not value:
        return ""
    f = get_fernet()
    return f.encrypt(value.encode()).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string."""
    if not encrypted_value:
        return ""
    f = get_fernet()
    return f.decrypt(encrypted_value.encode()).decode()
