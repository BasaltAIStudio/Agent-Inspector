import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is required for encryption")
    try:
        return Fernet(secret_key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("SECRET_KEY must be a valid Fernet key") from exc


def encryption_configured() -> bool:
    return bool(os.getenv("SECRET_KEY"))


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored secret could not be decrypted") from exc


def encrypt_to_str(plaintext: str) -> str:
    return encrypt(plaintext).decode("utf-8")


def decrypt_from_str(token: str) -> str:
    return decrypt(token.encode("utf-8"))
