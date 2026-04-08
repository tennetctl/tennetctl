"""Unit tests for 04_backend/02_features/iam/auth/password.py."""

import importlib

_password = importlib.import_module("04_backend.02_features.iam.auth.password")
hash_password = _password.hash_password
verify_password = _password.verify_password


def test_hash_returns_argon2id_phc_string():
    phc = hash_password("correct horse battery staple!")
    assert phc.startswith("$argon2id$")


def test_same_plaintext_produces_different_hashes():
    """Each hash call generates a new random salt."""
    plain = "correct horse battery staple!"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2


def test_verify_correct_password():
    plain = "CorrectPassword123!"
    phc = hash_password(plain)
    assert verify_password(phc, plain) is True


def test_verify_wrong_password():
    phc = hash_password("CorrectPassword123!")
    assert verify_password(phc, "WrongPassword999!") is False


def test_verify_never_raises_on_garbage():
    assert verify_password("not-a-valid-phc-string", "anything") is False
    assert verify_password("", "anything") is False


def test_hash_fits_in_text_column():
    """PHC string must be <= 200 chars to fit comfortably in TEXT with varchar limits."""
    phc = hash_password("some password with special chars !@#$")
    assert len(phc) <= 200
