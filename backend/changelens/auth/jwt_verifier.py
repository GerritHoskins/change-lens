"""Offline JWT verification against deployment-supplied issuer, audience and trusted JWKS.

No discovery or key URL is taken from a token. Refreshing the trusted JWKS is `auth.jwks`, and
resolving the user and active membership is GUARD (`api.auth`); linking is later I-8 work.
Successful verification establishes a subject, not a tenant, membership or approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping
from urllib.parse import urlsplit

import jwt

ALGORITHMS = {"RS256": "RSA", "PS256": "RSA", "ES256": "EC"}
SCOPE_TOKEN = re.compile(r'[\x21\x23-\x5b\x5d-\x7e]+\Z')


class AccessTokenRejected(Exception):
    def __init__(self):
        super().__init__("invalid_access_token")


@dataclass(frozen=True)
class JwtPolicy:
    issuer: str
    audience: str
    algorithms: tuple[str, ...] = ("RS256",)
    required_scopes: frozenset[str] = frozenset()
    leeway_seconds: int = 30
    max_lifetime_seconds: int = 900

    def __post_init__(self):
        try:
            url = urlsplit(self.issuer)
            valid = (isinstance(self.issuer, str) and self.issuer == self.issuer.strip()
                     and url.scheme == "https" and bool(url.hostname) and not url.username and not url.password
                     and not url.query and not url.fragment and isinstance(self.audience, str)
                     and bool(self.audience.strip()) and isinstance(self.algorithms, tuple)
                     and bool(self.algorithms) and len(set(self.algorithms)) == len(self.algorithms)
                     and all(alg in ALGORITHMS for alg in self.algorithms)
                     and isinstance(self.required_scopes, frozenset)
                     and all(isinstance(scope, str) and SCOPE_TOKEN.fullmatch(scope) for scope in self.required_scopes)
                     and type(self.leeway_seconds) is int and 0 <= self.leeway_seconds <= 60
                     and type(self.max_lifetime_seconds) is int and 1 <= self.max_lifetime_seconds <= 900)
        except (TypeError, ValueError, AttributeError):
            valid = False
        if not valid:
            raise ValueError("invalid_jwt_policy")


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str = field(repr=False)
    issuer: str
    audience: str
    scopes: frozenset[str]
    expires_at: int


class JwtVerifier:
    def __init__(self, policy: JwtPolicy, jwks: Mapping):
        self.policy = policy
        self._keys = {}
        try:
            keys = jwks["keys"]
            if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
                raise ValueError()
            for data in keys:
                if not isinstance(data, dict):
                    raise ValueError()
                kid, algorithm = data.get("kid"), data.get("alg")
                if (not isinstance(kid, str) or not 1 <= len(kid) <= 200 or kid in self._keys
                        or algorithm not in policy.algorithms or data.get("kty") != ALGORITHMS[algorithm]
                        or data.get("use", "sig") != "sig"
                        or data.get("key_ops", ["verify"]) != ["verify"]
                        or set(data) & {"d", "p", "q", "dp", "dq", "qi", "oth", "k"}):
                    raise ValueError()
                if algorithm == "ES256" and data.get("crv") != "P-256":
                    raise ValueError()
                key = jwt.PyJWK.from_dict(data, algorithm=algorithm)
                if data["kty"] == "RSA" and key.key.key_size < 2048:
                    raise ValueError()
                self._keys[kid] = key
        except (KeyError, TypeError, ValueError, AttributeError, jwt.PyJWTError):
            raise ValueError("invalid_trusted_jwks") from None

    @property
    def key_ids(self) -> frozenset[str]:
        return frozenset(self._keys)

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 16384:
                raise AccessTokenRejected()
            header = jwt.get_unverified_header(token)
            if set(header) & {"jku", "jwk", "x5u", "x5c", "crit"}:
                raise AccessTokenRejected()
            if header.get("typ") not in (None, "JWT", "at+jwt"):
                raise AccessTokenRejected()
            kid, algorithm = header.get("kid"), header.get("alg")
            if not isinstance(kid, str) or algorithm not in self.policy.algorithms:
                raise AccessTokenRejected()
            key = self._keys.get(kid)
            if key is None or key.algorithm_name != algorithm:
                raise AccessTokenRejected()
            claims = jwt.decode(token, key.key, algorithms=list(self.policy.algorithms),
                issuer=self.policy.issuer, audience=self.policy.audience, leeway=self.policy.leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"], "verify_signature": True,
                         "verify_exp": True, "verify_iat": True, "verify_nbf": True,
                         "verify_iss": True, "verify_aud": True, "strict_aud": True, "verify_sub": True})
            if any(type(claims.get(name)) is not int or claims[name] < 0 for name in ("exp", "iat")):
                raise AccessTokenRejected()
            if not 0 < claims["exp"] - claims["iat"] <= self.policy.max_lifetime_seconds:
                raise AccessTokenRejected()
            if "nbf" in claims and (type(claims["nbf"]) is not int or not 0 <= claims["nbf"] < claims["exp"]):
                raise AccessTokenRejected()
            subject = claims["sub"]
            if not isinstance(subject, str) or not 1 <= len(subject) <= 200 or subject != subject.strip():
                raise AccessTokenRejected()
            scope = claims.get("scope", "")
            if not isinstance(scope, str):
                raise AccessTokenRejected()
            parts = scope.split(" ") if scope else []
            if any(not SCOPE_TOKEN.fullmatch(part) for part in parts) or len(set(parts)) != len(parts):
                raise AccessTokenRejected()
            scopes = frozenset(parts)
            if not self.policy.required_scopes <= scopes:
                raise AccessTokenRejected()
            return VerifiedIdentity(subject, self.policy.issuer, self.policy.audience, scopes, claims["exp"])
        except (KeyError, TypeError, ValueError, OverflowError, jwt.PyJWTError):
            raise AccessTokenRejected() from None
