"""Shared auth module — JWT utilities."""

from .jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
    TokenData,
    TokenType,
)

# password.py (passlib/bcrypt) is NOT imported here — only api and upload
# need it. Import directly: from auth.password import hash_password, verify_password

__all__ = [
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token",
    "TokenData",
    "TokenType",
]
