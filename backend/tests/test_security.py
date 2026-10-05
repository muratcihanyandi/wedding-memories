import re
import secrets

import pytest

from app.security import hash_password, hash_token, new_token, verify_password


def test_password_roundtrip():
    stored = hash_password("dugun2026!")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("dugun2026!", stored) is True


def test_wrong_password_fails():
    stored = hash_password("dugun2026!")
    assert verify_password("yanlis", stored) is False


def test_malformed_hash_fails_closed():
    assert verify_password("herhangi", "bozuk-format") is False
    assert verify_password("herhangi", "") is False
    assert verify_password("herhangi", "pbkdf2_sha256$abc$zz$yy") is False


def test_salt_makes_hashes_unique():
    a = hash_password("ayni-sifre")
    b = hash_password("ayni-sifre")
    assert a != b
    assert verify_password("ayni-sifre", a)
    assert verify_password("ayni-sifre", b)


def test_hash_never_contains_password():
    stored = hash_password("gizli-sifre-123")
    assert "gizli" not in stored


def test_new_token_format_and_uniqueness():
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100
    for token in tokens:
        assert 40 <= len(token) <= 64
        assert re.fullmatch(r"[A-Za-z0-9_-]+", token)


def test_hash_token_deterministic_hex():
    token = new_token()
    assert hash_token(token) == hash_token(token)
    assert re.fullmatch(r"[0-9a-f]{64}", hash_token(token))
    assert hash_token(token) != hash_token(new_token())
