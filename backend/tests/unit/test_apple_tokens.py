"""AEAD tokens cannot be read under another identity/context or silently modified."""
import base64

import pytest

from changelens.auth.apple_tokens import AppleTokenCipher, TokenCipherError

CONTEXT = {"issuer": "https://identity.example.test", "subject": "synthetic-subject", "binding": "user:test-id"}
TEST_TOKEN = "synthetic-apple-refresh-token"


def cipher():
    return AppleTokenCipher({"test-key": b"A" * 32}, "test-key")


def test_token_round_trips_with_fresh_nonce_and_no_plaintext_in_envelope_or_repr():
    box = cipher()
    one, two = (box.encrypt(TEST_TOKEN, **CONTEXT) for _ in range(2))
    assert one != two and TEST_TOKEN not in one and TEST_TOKEN not in repr(box)
    assert box.decrypt(one, **CONTEXT) == box.decrypt(two, **CONTEXT) == TEST_TOKEN
    assert len(base64.urlsafe_b64decode(one.split(".")[2])[:12]) == 12


@pytest.mark.parametrize("field,value", [
    ("issuer", "https://other-issuer.test"), ("subject", "another-subject"),
    ("binding", "park:synthetic-subject"),
])
def test_ciphertext_is_bound_to_issuer_identity_and_record(field, value):
    box = cipher()
    stored = box.encrypt(TEST_TOKEN, **CONTEXT)
    with pytest.raises(TokenCipherError, match="^invalid_token_envelope$"):
        box.decrypt(stored, **{**CONTEXT, field: value})


def test_rotation_decrypts_old_tokens_but_encrypts_with_active_key():
    old = cipher().encrypt(TEST_TOKEN, **CONTEXT)
    rotated = AppleTokenCipher({"test-key": b"A" * 32, "next": b"B" * 32}, "next")
    assert rotated.decrypt(old, **CONTEXT) == TEST_TOKEN
    new = rotated.encrypt(TEST_TOKEN, **CONTEXT)
    assert new.startswith("v1.next.")
    assert AppleTokenCipher({"next": b"B" * 32}, "next").decrypt(new, **CONTEXT) == TEST_TOKEN
    with pytest.raises(TokenCipherError):
        AppleTokenCipher({"next": b"B" * 32}, "next").decrypt(old, **CONTEXT)


def test_tampering_nonce_ciphertext_tag_key_id_and_wrong_key_are_rejected():
    box = cipher()
    original = box.encrypt(TEST_TOKEN, **CONTEXT)
    version, kid, payload = original.split(".")
    for offset in (0, 12, -1):
        raw = bytearray(base64.urlsafe_b64decode(payload))
        raw[offset] ^= 1
        changed = f"{version}.{kid}." + base64.urlsafe_b64encode(raw).decode()
        with pytest.raises(TokenCipherError):
            box.decrypt(changed, **CONTEXT)
    with pytest.raises(TokenCipherError):
        AppleTokenCipher({"test-key": b"B" * 32}, "test-key").decrypt(original, **CONTEXT)
    # Even aliasing the same material under another key ID does not permit envelope relabelling.
    aliases = AppleTokenCipher({"test-key": b"A" * 32, "alias": b"A" * 32}, "alias")
    with pytest.raises(TokenCipherError):
        aliases.decrypt(original.replace(".test-key.", ".alias."), **CONTEXT)


@pytest.mark.parametrize("value", ["", "v0.key.abc", "v1.unknown.abc", "v1.test-key.@@@", "one.two", "x" * 24001, None])
def test_invalid_envelopes_fail_without_echoing_inputs(value):
    with pytest.raises(TokenCipherError, match="^invalid_token_envelope$"):
        cipher().decrypt(value, **CONTEXT)


@pytest.mark.parametrize("keys,active", [
    ({}, "a"), ({"a": b"A" * 16}, "a"), ({"a": b"A" * 32}, "missing"),
    ({"a": "A" * 32}, "a"), ({"unsafe.id": b"A" * 32}, "unsafe.id"),
])
def test_only_explicit_256_bit_secret_keyrings_are_accepted(keys, active):
    with pytest.raises(ValueError, match="^invalid_token_keyring$"):
        AppleTokenCipher(keys, active)


@pytest.mark.parametrize("token", ["", "x" * 16385, None, "\ud800"])
def test_empty_or_oversized_tokens_are_not_encrypted(token):
    with pytest.raises(TokenCipherError):
        cipher().encrypt(token, **CONTEXT)


def test_missing_context_cannot_create_unbound_ciphertext():
    for subject in ("", "\ud800"):
        with pytest.raises(TokenCipherError):
            cipher().encrypt(TEST_TOKEN, **{**CONTEXT, "subject": subject})
