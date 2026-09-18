import os
import base64
import hashlib

def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        secret = os.environ.get('SECRET_KEY', 'flyash-default-encryption-secret-key-32b').encode('utf-8')
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
        return Fernet(derived_key)
    except Exception:
        return None

def encrypt_secret(plain_text):
    """Encrypts plaintext secret at rest."""
    if not plain_text:
        return ''
    if str(plain_text).startswith('enc:'):
        return plain_text  # Already encrypted
    f = _get_fernet()
    if f:
        try:
            return 'enc:' + f.encrypt(str(plain_text).encode('utf-8')).decode('utf-8')
        except Exception:
            return str(plain_text)
    return str(plain_text)

def decrypt_secret(cipher_text):
    """Decrypts secret for in-memory use."""
    if not cipher_text:
        return ''
    if str(cipher_text).startswith('enc:'):
        f = _get_fernet()
        if f:
            try:
                raw_cipher = str(cipher_text)[4:].encode('utf-8')
                return f.decrypt(raw_cipher).decode('utf-8')
            except Exception:
                return ''
    return str(cipher_text)
