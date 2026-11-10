"""Versioned, context-bound AEAD storage for Apple's refresh tokens (I-8/AR-1..5).

The caller supplies a secret keyring; this module never generates/persists keys, reads environment
variables or calls Apple. Deletion/revocation and the one-hour parked-token lifecycle are separate.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
from typing import Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class TokenCipherError(Exception):
    def __init__(self):
        super().__init__("invalid_token_envelope")


class AppleTokenCipher:
    def __init__(self, keys: Mapping[str, bytes], active_key_id: str):
        if (not isinstance(keys, Mapping) or not keys or len(keys) > 16
                or not isinstance(active_key_id, str) or active_key_id not in keys
                or any(not isinstance(k, str) or not KEY_ID.fullmatch(k) or type(v) is not bytes or len(v) != 32
                       for k, v in keys.items())):
            raise ValueError("invalid_token_keyring")
        self._keys = {name: AESGCM(key) for name, key in keys.items()}
        self._active = active_key_id

    @staticmethod
    def _context(issuer: str, subject: str, binding: str, key_id: str) -> bytes:
        # binding distinguishes a user's immutable row ID from a parked Logto-subject record.
        if any(not isinstance(v, str) or not 1 <= len(v) <= 500 for v in (issuer, subject, binding)):
            raise TokenCipherError()
        return json.dumps(["changelens/apple-refresh/v1", key_id, issuer, subject, binding],
                          separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def encrypt(self, token: str, *, issuer: str, subject: str, binding: str) -> str:
        try:
            if not isinstance(token, str) or not 1 <= len(token.encode("utf-8")) <= 16384:
                raise TokenCipherError()
            context = self._context(issuer, subject, binding, self._active)
        except UnicodeError:
            raise TokenCipherError() from None
        nonce = secrets.token_bytes(12)
        encrypted = self._keys[self._active].encrypt(nonce, token.encode("utf-8"), context)
        payload = base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
        return f"v1.{self._active}.{payload}"

    def decrypt(self, envelope: str, *, issuer: str, subject: str, binding: str) -> str:
        try:
            if not isinstance(envelope, str) or not 1 <= len(envelope) <= 24000:
                raise TokenCipherError()
            version, key_id, payload = envelope.split(".")
            if version != "v1" or key_id not in self._keys:
                raise TokenCipherError()
            context = self._context(issuer, subject, binding, key_id)
            raw = base64.b64decode(payload.encode("ascii"), altchars=b"-_", validate=True)
            if len(raw) < 29 or base64.urlsafe_b64encode(raw).decode("ascii") != payload:
                raise TokenCipherError()
            token = self._keys[key_id].decrypt(raw[:12], raw[12:], context).decode("utf-8")
            if not 1 <= len(token.encode("utf-8")) <= 16384:
                raise TokenCipherError()
            return token
        except (ValueError, TypeError, UnicodeError, binascii.Error, InvalidTag):
            raise TokenCipherError() from None
