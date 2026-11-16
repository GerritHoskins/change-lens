"""Offline trust-boundary tests using ephemeral signing keys, never live identities."""
import json
import time
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric import ec, rsa
import jwt
import pytest

from changelens.auth.jwt_verifier import AccessTokenRejected, JwtPolicy, JwtVerifier

ISSUER = "https://identity.example.test/oidc"
AUDIENCE = "https://api.example.test"


@pytest.fixture(scope="module")
def signing():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public.update(kid="test-key", alg="RS256", use="sig", key_ops=["verify"])
    return key, public


@pytest.fixture()
def verifier(signing):
    return JwtVerifier(JwtPolicy(ISSUER, AUDIENCE, required_scopes=frozenset({"compare:read"})),
                       {"keys": [signing[1]]})


def claims(**changes):
    now = int(time.time())
    return {"iss": ISSUER, "aud": AUDIENCE, "sub": "synthetic-subject", "iat": now - 5,
            "nbf": now - 5, "exp": now + 300, "scope": "compare:read compare:write", **changes}


def token(signing, payload=None, headers=None, algorithm="RS256"):
    return jwt.encode(payload or claims(), signing[0], algorithm=algorithm,
                      headers={"kid": "test-key", **(headers or {})})


def test_verified_identity_has_no_raw_token_tenant_or_document_claims(signing, verifier):
    raw = token(signing, claims(email="private@example.test", tenant_id="untrusted-tenant"))
    identity = verifier.verify(raw)
    assert identity.subject == "synthetic-subject" and identity.scopes == frozenset({"compare:read", "compare:write"})
    assert not hasattr(identity, "tenant_id") and not hasattr(identity, "email")
    assert "synthetic-subject" not in repr(identity) and raw not in repr(identity)


@pytest.mark.parametrize("update", [
    {"iss": "https://identity.example.test/other"}, {"iss": ISSUER + "/"},
    {"aud": "another-audience"}, {"aud": [AUDIENCE]}, {"aud": [AUDIENCE, "other"]},
    # Time-relative cases are callables so they use the run-time clock, as claims() does;
    # values fixed at collection time drift as the suite runs (exp + 901 fell under the cap).
    {"exp": 1}, lambda now: {"iat": now + 300}, lambda now: {"nbf": now + 300},
    lambda now: {"exp": now + 901}, {"iat": "123"}, {"iat": True},
    {"nbf": "123"}, {"nbf": False}, lambda now: {"exp": str(now + 300)},
    {"sub": ""}, {"sub": " has-space "}, {"sub": 1},
    {"scope": ["compare:read"]}, {"scope": "compare:write"},
    {"scope": "compare:read  compare:write"}, {"scope": "compare:read\ncompare:write"},
    {"scope": "compare:read compare:read"},
])
def test_claim_policy_rejects_wrong_issuer_audience_time_subject_or_scope(signing, verifier, update):
    if callable(update):
        update = update(int(time.time()))
    with pytest.raises(AccessTokenRejected, match="^invalid_access_token$"):
        verifier.verify(token(signing, claims(**update)))


@pytest.mark.parametrize("missing", ["iss", "aud", "sub", "exp", "iat"])
def test_security_claims_are_required(signing, verifier, missing):
    payload = claims()
    del payload[missing]
    with pytest.raises(AccessTokenRejected):
        verifier.verify(token(signing, payload))


def test_nbf_is_optional_but_validated_when_present(signing, verifier):
    payload = claims()
    del payload["nbf"]
    assert verifier.verify(token(signing, payload)).subject == "synthetic-subject"


@pytest.mark.parametrize("headers", [
    {"kid": "unknown"}, {"kid": ""}, {"jku": "https://attacker.test/keys"},
    {"jwk": {"kty": "oct", "k": "attacker"}}, {"x5u": "https://attacker.test/cert"},
    {"crit": []}, {"typ": "id-token"},
])
def test_token_headers_cannot_select_untrusted_keys_or_unsupported_policy(signing, verifier, headers):
    with pytest.raises(AccessTokenRejected):
        verifier.verify(token(signing, headers=headers))


def test_signature_is_checked_and_algorithm_cannot_be_downgraded(signing, verifier):
    different = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(claims(), different, algorithm="RS256", headers={"kid": "test-key"})
    unsigned = jwt.encode(claims(), None, algorithm="none", headers={"kid": "test-key"})
    symmetric = jwt.encode(claims(), b"test-only-nonproduction-value-32xx", algorithm="HS256", headers={"kid": "test-key"})
    for value in (forged, unsigned, symmetric, "not-a-jwt", "x" * 16385, None):
        with pytest.raises(AccessTokenRejected):
            verifier.verify(value)


@pytest.mark.parametrize("changes", [
    {"issuer": "http://identity.example.test"}, {"issuer": "https://user:pass@identity.example.test"},
    {"issuer": "https://identity.example.test?query=1"}, {"audience": ""},
    {"algorithms": ("HS256",)}, {"algorithms": ("none",)}, {"algorithms": ()},
    {"algorithms": ("RS256", "RS256")}, {"leeway_seconds": 61},
    {"max_lifetime_seconds": 901}, {"required_scopes": frozenset({"two scopes"})},
])
def test_invalid_deployment_policy_fails_before_accepting_tokens(changes):
    with pytest.raises(ValueError, match="^invalid_jwt_policy$"):
        replace(JwtPolicy(ISSUER, AUDIENCE), **changes)


@pytest.mark.parametrize("change", [
    {"alg": "HS256"}, {"use": "enc"}, {"key_ops": ["sign"]}, {"d": "private-material"},
    {"kid": None}, {"kty": "oct"},
])
def test_jwks_must_contain_only_eligible_public_verification_keys(signing, change):
    with pytest.raises(ValueError, match="^invalid_trusted_jwks$"):
        JwtVerifier(JwtPolicy(ISSUER, AUDIENCE), {"keys": [{**signing[1], **change}]})


def test_duplicate_kid_and_weak_rsa_keys_are_rejected(signing):
    policy = JwtPolicy(ISSUER, AUDIENCE)
    with pytest.raises(ValueError):
        JwtVerifier(policy, {"keys": [signing[1], signing[1]]})
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(weak.public_key()))
    jwk.update(kid="weak", alg="RS256")
    with pytest.raises(ValueError):
        JwtVerifier(policy, {"keys": [jwk]})


def test_es256_requires_matching_curve_and_explicit_deployment_algorithm():
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="ec", alg="ES256")
    verifier = JwtVerifier(JwtPolicy(ISSUER, AUDIENCE, algorithms=("ES256",)), {"keys": [jwk]})
    signed = jwt.encode(claims(), key, algorithm="ES256", headers={"kid": "ec"})
    assert verifier.verify(signed).subject == "synthetic-subject"
    with pytest.raises(ValueError):
        JwtVerifier(JwtPolicy(ISSUER, AUDIENCE), {"keys": [jwk]})


def test_jwk_without_alg_is_accepted_only_when_the_key_type_fits_one_allowed_algorithm(signing):
    # Logto publishes its RSA key without "alg" (seen on the I-8 S7 deployment).
    bare = {k: v for k, v in signing[1].items() if k != "alg"}
    verifier = JwtVerifier(JwtPolicy(ISSUER, AUDIENCE), {"keys": [bare]})
    assert verifier.verify(token(signing)).subject == "synthetic-subject"
    with pytest.raises(AccessTokenRejected):
        verifier.verify(token(signing, algorithm="PS256"))
    with pytest.raises(ValueError, match="^invalid_trusted_jwks$"):
        JwtVerifier(JwtPolicy(ISSUER, AUDIENCE, algorithms=("RS256", "PS256")), {"keys": [bare]})
    with pytest.raises(ValueError, match="^invalid_trusted_jwks$"):
        JwtVerifier(JwtPolicy(ISSUER, AUDIENCE, algorithms=("ES256",)), {"keys": [bare]})


def test_trusted_key_rotation_uses_new_verifier_snapshot_without_fetching(signing):
    current = JwtVerifier(JwtPolicy(ISSUER, AUDIENCE), {"keys": [signing[1]]})
    next_jwk = {**signing[1], "kid": "next"}
    rotated = JwtVerifier(JwtPolicy(ISSUER, AUDIENCE), {"keys": [signing[1], next_jwk]})
    signed = token(signing, headers={"kid": "next"})
    with pytest.raises(AccessTokenRejected):
        current.verify(signed)
    assert rotated.verify(signed).subject == "synthetic-subject"
