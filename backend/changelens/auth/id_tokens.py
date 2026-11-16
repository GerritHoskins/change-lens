"""Google and Apple ID tokens from the backend's own code exchange (I-8 S4; O-19, ADR-0020).

Verified offline against the provider's published keys, which `auth.jwks` fetches from a configured URL:
signature, issuer, audience (our client ID), expiry, issued-at and token age, and the nonce when the flow
has one. The email comes only from a verified token, and only when the provider marks it verified.
Errors carry an event code only: never a claim, subject, email or token.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional

import jwt

from changelens.auth.jwt_verifier import load_jwks

ALGORITHMS = ("RS256",)  # Google and Apple sign ID tokens with RS256
MAX_SUBJECT = 255
MAX_EMAIL = 320


class IdTokenRejected(Exception):
    def __init__(self):
        super().__init__("invalid_id_token")


@dataclass(frozen=True)
class IdTokenPolicy:
    provider: str
    issuers: tuple[str, ...]
    audience: str
    nonce_hashed: bool  # Apple: the app gives Apple SHA-256(nonce) and sends the raw nonce to us
    max_lifetime_seconds: int
    max_age_seconds: int = 600  # the token was just issued by our own code exchange
    leeway_seconds: int = 30

    def __post_init__(self):
        if (not self.issuers or not all(isinstance(i, str) and i for i in self.issuers)
                or not isinstance(self.audience, str) or not self.audience.strip()):
            raise ValueError("invalid_id_token_policy")


GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
APPLE_ISSUER = "https://appleid.apple.com"


def google_policy(client_id: str) -> IdTokenPolicy:
    return IdTokenPolicy("google", GOOGLE_ISSUERS, client_id, nonce_hashed=False, max_lifetime_seconds=3600)


def apple_policy(client_id: str) -> IdTokenPolicy:
    return IdTokenPolicy("apple", (APPLE_ISSUER,), client_id, nonce_hashed=True, max_lifetime_seconds=86400)


@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    subject: str = field(repr=False)
    email: Optional[str] = field(default=None, repr=False)  # set only when the provider verified it


def _verified(value) -> bool:
    return value is True or value == "true"  # Apple may send the string


class IdTokenVerifier:
    def __init__(self, policy: IdTokenPolicy, jwks: Mapping, clock: Callable[[], float] = time.time):
        self.policy = policy
        self._clock = clock
        self._keys = load_jwks(ALGORITHMS, jwks, lambda kty: "RS256" if kty == "RSA" else None)

    @property
    def key_ids(self) -> frozenset[str]:
        return frozenset(self._keys)

    def verify(self, token: str, nonce: Optional[str] = None) -> ProviderIdentity:
        p = self.policy
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 16384:
                raise IdTokenRejected()
            header = jwt.get_unverified_header(token)
            if set(header) & {"jku", "jwk", "x5u", "x5c", "crit"}:
                raise IdTokenRejected()
            key = self._keys.get(header.get("kid"))
            if key is None or header.get("alg") not in ALGORITHMS or key.algorithm_name != header.get("alg"):
                raise IdTokenRejected()
            claims = jwt.decode(token, key.key, algorithms=list(ALGORITHMS), audience=p.audience,
                                leeway=p.leeway_seconds,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"], "verify_signature": True,
                                         "verify_exp": True, "verify_iat": True, "verify_aud": True,
                                         "strict_aud": True, "verify_iss": False})
            if claims["iss"] not in p.issuers:
                raise IdTokenRejected()
            if any(type(claims.get(name)) is not int for name in ("exp", "iat")):
                raise IdTokenRejected()
            if not 0 < claims["exp"] - claims["iat"] <= p.max_lifetime_seconds:
                raise IdTokenRejected()
            if self._clock() - claims["iat"] > p.max_age_seconds + p.leeway_seconds:
                raise IdTokenRejected()
            subject = claims["sub"]
            if not isinstance(subject, str) or not 1 <= len(subject) <= MAX_SUBJECT or subject != subject.strip():
                raise IdTokenRejected()
            self._check_nonce(claims.get("nonce"), nonce)
            email = claims.get("email")
            if not (_verified(claims.get("email_verified")) and isinstance(email, str)
                    and 3 <= len(email) <= MAX_EMAIL and "@" in email and email == email.strip()):
                email = None
            return ProviderIdentity(p.provider, subject, email)
        except (KeyError, TypeError, ValueError, OverflowError, jwt.PyJWTError):
            raise IdTokenRejected() from None

    def _check_nonce(self, claim, nonce: Optional[str]) -> None:
        if nonce is None and claim is None:
            return
        if not isinstance(nonce, str) or not isinstance(claim, str):
            raise IdTokenRejected()  # a nonce on only one side is a mismatch
        expected = hashlib.sha256(nonce.encode("utf-8")).hexdigest() if self.policy.nonce_hashed else nonce
        if not hmac.compare_digest(expected.encode("utf-8"), claim.encode("utf-8")):
            raise IdTokenRejected()
