import pytest
import os
from app.crypto import encrypt_value, decrypt_value
from cryptography.fernet import Fernet

def test_encryption_decryption(monkeypatch):
    # Setup a dummy key for testing
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_MASTER_KEY", test_key)
    
    # Reload the master key in the module
    import app.crypto
    monkeypatch.setattr(app.crypto, "MASTER_KEY", test_key)

    secret = "my-super-secret-123"
    encrypted = encrypt_value(secret)
    assert encrypted != secret
    assert isinstance(encrypted, str)

    decrypted = decrypt_value(encrypted)
    assert decrypted == secret

def test_encryption_empty_value():
    assert encrypt_value("") == ""
    assert decrypt_value("") == ""

def test_encryption_missing_key(monkeypatch):
    import app.crypto
    monkeypatch.setattr(app.crypto, "MASTER_KEY", "")
    
    with pytest.raises(ValueError, match="ENCRYPTION_MASTER_KEY is missing"):
        encrypt_value("test")
