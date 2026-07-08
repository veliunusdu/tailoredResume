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

def get_user_fernet(user_id: str) -> Fernet:
    """
    Get or create a per-user Fernet key, envelope-encrypted by the MASTER_KEY.
    """
    from app.db import get_connection
    if not MASTER_KEY:
        raise ValueError("ENCRYPTION_MASTER_KEY is missing from .env")
        
    master_f = Fernet(MASTER_KEY.encode())
    
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT encrypted_data_key FROM user_keys WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            
            if row:
                user_key = master_f.decrypt(row[0].encode())
                return Fernet(user_key)
            
            # Generate new key for user
            new_key = Fernet.generate_key()
            encrypted_key = master_f.encrypt(new_key).decode()
            
            cur.execute(
                "INSERT INTO user_keys (user_id, encrypted_data_key) VALUES (%s, %s)",
                (user_id, encrypted_key)
            )
            return Fernet(new_key)

def encrypt_user_value(user_id: str, value: str) -> str:
    if not value:
        return ""
    f = get_user_fernet(user_id)
    return f.encrypt(value.encode()).decode()

def decrypt_user_value(user_id: str, encrypted_value: str) -> str:
    if not encrypted_value:
        return ""
    try:
        f = get_user_fernet(user_id)
        return f.decrypt(encrypted_value.encode()).decode()
    except Exception:
        # Fallback to master key decryption for backwards compatibility if needed
        # (Though we shouldn't mix, it's safer for existing single-user sessions)
        try:
            return decrypt_value(encrypted_value)
        except Exception:
            return ""
