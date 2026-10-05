"""Sifre hashing ve token uretimi.

pbkdf2_hmac secildi: stdlib, ARM64 native derleme gerektirmez,
bcrypt argon2 kadar hizli degil ama 600k iterasyonla yeterince guclu.
Hash formati: pbkdf2_sha256$<iterasyon>$<salt_hex>$<hash_hex>
"""

import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != _ALGO:
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if iterations < 1 or not salt or not expected:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def new_token() -> str:
    """43 karakter urlsafe rastgele token (~256 bit entropi)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Token'in DB'de saklanan sha256 ozeti - token sizilirsa bile
    dogrudan oturum calmak mumkun olmaz."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
