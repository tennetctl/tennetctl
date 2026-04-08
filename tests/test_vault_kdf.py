"""Unit tests for scripts/setup/vault_init/kdf.py."""

import importlib

_kdf = importlib.import_module("scripts.setup.vault_init.kdf")
new_salt = _kdf.new_salt
derive_wrap_key = _kdf.derive_wrap_key
blake2b_hex = _kdf.blake2b_hex


def test_new_salt_is_16_bytes():
    salt = new_salt()
    assert isinstance(salt, bytes)
    assert len(salt) == 16


def test_new_salt_is_random():
    salts = {new_salt() for _ in range(10)}
    assert len(salts) == 10, "Expected all salts to be unique"


def test_derive_wrap_key_is_32_bytes():
    key = derive_wrap_key("password", new_salt())
    assert isinstance(key, bytes)
    assert len(key) == 32


def test_derive_wrap_key_is_deterministic():
    salt = new_salt()
    key1 = derive_wrap_key("same_password", salt)
    key2 = derive_wrap_key("same_password", salt)
    assert key1 == key2


def test_derive_wrap_key_differs_on_different_salt():
    key1 = derive_wrap_key("password", new_salt())
    key2 = derive_wrap_key("password", new_salt())
    assert key1 != key2


def test_derive_wrap_key_differs_on_different_password():
    salt = new_salt()
    key1 = derive_wrap_key("password_a", salt)
    key2 = derive_wrap_key("password_b", salt)
    assert key1 != key2


def test_blake2b_hex_returns_64_char_hex():
    digest = blake2b_hex(b"hello")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_blake2b_hex_is_deterministic():
    assert blake2b_hex(b"hello") == blake2b_hex(b"hello")


def test_blake2b_hex_differs_on_different_input():
    assert blake2b_hex(b"hello") != blake2b_hex(b"world")
