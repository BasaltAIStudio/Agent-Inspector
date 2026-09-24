import os
from cryptography.fernet import Fernet, InvalidToken

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required for encryption")

fernet = Fernet(SECRET_KEY.encode())


def encrypt(plaintext: str) -> bytes:
    return fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes) -> str:
    return fernet.decrypt(token).decode("utf-8")


def encrypt_to_str(plaintext: str) -> str:
    return encrypt(plaintext).decode("utf-8")


def decrypt_from_str(token: str) -> str:
    return decrypt(token.encode("utf-8"))
