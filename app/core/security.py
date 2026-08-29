from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class EncryptionError(Exception):
    pass


def encrypt(plaintext: str, key: bytes) -> str:
    return Fernet(key).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, key: bytes) -> str:
    try:
        return Fernet(key).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        # Rotating AI_CONFIG_ENCRYPTION_KEY orphans every key stored under the old
        # one. That is recoverable (re-enter the key) but only if it is legible.
        raise EncryptionError(
            "Stored value cannot be decrypted with the current AI_CONFIG_ENCRYPTION_KEY"
        ) from exc


def get_ai_config_key() -> bytes:
    return get_settings().ai_config_encryption_key.encode()
