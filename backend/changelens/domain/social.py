"""Native Google and Apple sign-in, backend-owned linking and Apple tokens (03a P1 and P8; I-8 S4, O-19).

`POST /session` without a bearer (`provider_sign_in`):
1. the provider client exchanges the code once and verifies the ID token (`auth.social`);
2. the Logto user holding that identity signs in;
3. otherwise a Logto user with the same verified email gets a pending link and the caller `link_required`:
   nothing is signed in or created, and a matching email alone never links (SA-3, AC-26);
4. otherwise a new Logto user is created with the email and the identity (sign-up cap first).
On 2 and 4 the Apple refresh token is parked under the Logto subject and Logto issues a single-use token
that the app redeems in Logto's normal sign-in, where the user's MFA applies.

`POST /session` with a bearer then attaches the parked token to the user row (`attach_parked`), or, with a
`link_id`, completes the link (`take_link`, `complete_link`): only when the signed-in subject is the link's
target, before expiry, once. Any other outcome deletes the pending link and expires its parked token.

Apple tokens are AES-GCM envelopes (`auth.apple_tokens`): bound to the user ID on the user row and to the
park ID while parked. Maintenance revokes expired parks with Apple and deletes them only once Apple
confirms (AR-5, AR-6); account deletion revokes the user's token first (AR-1).

Pre-tenant tables, reached through the functions of migration 0006 only. Logs carry event codes only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from changelens.auth.apple_tokens import AppleTokenCipher, TokenCipherError
from changelens.auth.id_tokens import APPLE_ISSUER
from changelens.auth.logto_management import IdentityInUse, IdpUnavailable, sign_in_methods
from changelens.auth.social import (AppleRevokeFailed, ProviderRejected, apple_client, providers_for,
                                    token_cipher_from_file)

log = logging.getLogger("changelens.social")

PARK_TTL = timedelta(hours=1)  # AR-5
LINK_TTL = timedelta(hours=1)
ONE_TIME_TOKEN_SECONDS = 120


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkRejected(Exception):
    """Mismatch, expiry, reuse or a refused link: the caller answers 401."""


class SocialRepo:
    """Parked Apple tokens and pending links, through the SECURITY DEFINER functions of migration 0006."""

    def __init__(self, session: Session):
        self.s = session

    def _run(self, sql: str, **params):
        return self.s.execute(text(sql), params)

    def park(self, park_id: uuid.UUID, subject: Optional[str], envelope: str, expires_at: datetime) -> None:
        self._run("SELECT apple_park_put(:i, :s, :t, :e)", i=park_id, s=subject, t=envelope, e=expires_at)

    def parks_for(self, subject: str) -> list:
        return list(self._run("SELECT park_id, token_enc FROM apple_parks_for(:s)", s=subject))

    def attach(self, user_id: uuid.UUID, subject: str, park_id: uuid.UUID, envelope: str) -> bool:
        return self._run("SELECT apple_park_attach(:u, :s, :p, :t)", u=user_id, s=subject, p=park_id,
                         t=envelope).scalar_one()

    def expire_park(self, park_id: uuid.UUID) -> None:
        self._run("SELECT apple_park_expire(:p)", p=park_id)

    def parks_due(self, now: datetime, limit: int) -> list:
        return list(self._run("SELECT park_id, token_enc, attempts FROM apple_parks_due(:n, :l)", n=now, l=limit))

    def park_revoked(self, park_id: uuid.UUID) -> bool:
        return self._run("SELECT apple_park_revoked(:p)", p=park_id).scalar_one()

    def park_retry(self, park_id: uuid.UUID, next_at: datetime) -> None:
        self._run("SELECT apple_park_retry(:p, :n)", p=park_id, n=next_at)

    def put_link(self, link_id: uuid.UUID, provider: str, provider_subject: str, target: str,
                 park_id: Optional[uuid.UUID], expires_at: datetime) -> None:
        self._run("SELECT pending_link_put(:i, :p, :ps, :t, :k, :e)", i=link_id, p=provider, ps=provider_subject,
                  t=target, k=park_id, e=expires_at)

    def take_link(self, link_id: uuid.UUID):
        return self._run("SELECT provider, provider_subject, target_subject, park_id, park_token, expired "
                         "FROM pending_link_take(:i)", i=link_id).one_or_none()

    def prune_links(self, now: datetime) -> int:
        return self._run("SELECT pending_links_prune(:n)", n=now).scalar_one()


class AppleTokens:
    """Envelopes for Apple refresh tokens, and revocation. `client` is `auth.social.AppleClient` (or a fake)."""

    def __init__(self, cipher: AppleTokenCipher, client=None):
        self.cipher, self.client = cipher, client

    def seal_park(self, token: str, park_id: uuid.UUID) -> str:
        return self.cipher.encrypt(token, issuer=APPLE_ISSUER, subject=str(park_id), binding="park")

    def open_park(self, envelope: str, park_id: uuid.UUID) -> str:
        return self.cipher.decrypt(envelope, issuer=APPLE_ISSUER, subject=str(park_id), binding="park")

    def seal_user(self, token: str, user_id: uuid.UUID) -> str:
        return self.cipher.encrypt(token, issuer=APPLE_ISSUER, subject=str(user_id), binding="user")

    def open_user(self, envelope: str, user_id: uuid.UUID) -> str:
        return self.cipher.decrypt(envelope, issuer=APPLE_ISSUER, subject=str(user_id), binding="user")

    def revoke(self, token: str) -> None:
        if self.client is None:
            raise AppleRevokeFailed("apple_not_configured")
        self.client.revoke(token)


def social_for(settings) -> tuple[dict, Optional[AppleTokens]]:
    """The sign-in providers by name, and Apple token handling (None without Apple), from settings. One
    Apple client serves both sign-in and revocation."""
    providers = providers_for(settings)
    if "apple" not in providers:
        return providers, None
    return providers, AppleTokens(token_cipher_from_file(settings.apple_token_keys_file), providers["apple"])


def apple_tokens_for(settings) -> Optional[AppleTokens]:
    """For the retention process: revocation only."""
    client = apple_client(settings)
    return AppleTokens(token_cipher_from_file(settings.apple_token_keys_file), client) if client else None


def _park(db, apple: Optional[AppleTokens], refresh: Optional[str], subject: Optional[str],
          now: datetime) -> Optional[uuid.UUID]:
    if refresh is None:
        return None
    if apple is None:
        raise IdpUnavailable("apple_token_keys_not_configured")  # never keep an Apple token unencrypted
    park_id = uuid.uuid4()
    with db.social_scope() as social:
        social.park(park_id, subject, apple.seal_park(refresh, park_id), now + PARK_TTL)
    return park_id


def provider_sign_in(db, idp, provider, apple: Optional[AppleTokens], code: str, nonce: Optional[str], *,
                     before_create: Callable[[], None], now: Optional[datetime] = None) -> dict:
    """03a P1 ON_SIGN_IN for Google and Apple. Raises ProviderRejected (401), ProviderUnavailable or
    IdpUnavailable (503). Returns the `POST /session` body."""
    now = now or utcnow()
    exchange = provider.exchange(code, nonce)  # the one exchange of this code
    identity, target = exchange.identity, provider.provider
    user = idp.user_by_identity(target, identity.subject)
    if user is None:
        existing = idp.user_by_email(identity.email)
        if existing is not None:
            linked = (existing.get("identities") or {}).get(target)
            if linked:  # the account already has another identity of this provider; never replace it
                raise ProviderRejected("provider_identity_conflict")
            park_id = _park(db, apple, exchange.refresh_token, None, now)
            link_id = uuid.uuid4()
            with db.social_scope() as social:
                social.put_link(link_id, target, identity.subject, existing["id"], park_id, now + LINK_TTL)
            log.info("social sign-in: link_required")
            return {"status": "link_required", "methods": sign_in_methods(existing), "link_id": str(link_id)}
        before_create()  # the sign-up cap for new identity-provider accounts (I-8 S6)
        try:
            user_id = idp.create_user(identity.email)
            idp.link_identity(user_id, target, identity.subject)
        except IdentityInUse:
            raise IdpUnavailable("sign_up_race") from None  # a concurrent sign-up won; the app retries
        user = {"id": user_id, "primaryEmail": identity.email}
        log.info("social sign-in: logto user created")
    email = user.get("primaryEmail")
    if not isinstance(email, str) or not email:
        raise IdpUnavailable("user_without_email")  # a one-time token needs the account's email
    _park(db, apple, exchange.refresh_token, user["id"], now)
    token = idp.one_time_token(email, ONE_TIME_TOKEN_SECONDS)
    log.info("social sign-in: one-time token issued")
    return {"status": "sign_in", "one_time_token": token, "login_hint": email, "expires_in": ONE_TIME_TOKEN_SECONDS}


def take_link(db, subject: str, link_id) -> tuple[str, str, Optional[tuple]]:
    """Use a pending link once. Returns (provider, provider subject, park) when `subject` is its target and
    it hasn't expired, `park` being (park ID, envelope) or None; otherwise its parked token is expired for
    revocation and LinkRejected is raised."""
    try:
        link_uuid = uuid.UUID(str(link_id))
    except ValueError:
        raise LinkRejected("malformed") from None
    with db.social_scope() as social:  # commits the deletion (and any expiry) before a rejection is raised
        row = social.take_link(link_uuid)
        rejected = row is None or row.expired or row.target_subject != subject
        if rejected and row is not None and row.park_id is not None:
            social.expire_park(row.park_id)
    if rejected:
        raise LinkRejected("unknown_or_used" if row is None else "expired" if row.expired else "subject_mismatch")
    park =(row.park_id, row.park_token) if row.park_id is not None and row.park_token else None
    return row.provider, row.provider_subject, park


def complete_link(db, idp, subject: str, provider: str, provider_subject: str, park: Optional[tuple]) -> None:
    """Link the identity to the signed-in user through the Management API (O-19). Refused links expire the
    parked token; a Logto outage propagates (503) and also expires it, since the link was used."""
    try:
        user = idp.user(subject)
        linked = ((user or {}).get("identities") or {}).get(provider)
        if user is None or (linked and linked.get("userId") != provider_subject):
            raise LinkRejected("target_changed")
        idp.link_identity(subject, provider, provider_subject)
    except (LinkRejected, IdentityInUse, IdpUnavailable) as exc:
        if park is not None:
            with db.social_scope() as social:
                social.expire_park(park[0])
        if isinstance(exc, IdpUnavailable):
            raise
        raise LinkRejected("refused") from None
    log.info("social sign-in: identity linked")


def attach_parked(db, apple: Optional[AppleTokens], user_id: uuid.UUID, subject: str,
                  park: Optional[tuple] = None) -> bool:
    """Move a parked Apple token onto the user row (AR-2): `park` (a completed link's (ID, envelope)), else
    the newest park of this subject. Other parks of the subject are expired for revocation. Never raises
    for a missing or unreadable park: the session still succeeds, and maintenance revokes what is left."""
    if apple is None:
        return False
    try:
        if park is None:
            with db.social_scope() as social:
                parks = social.parks_for(subject)
            if not parks:
                return False
            park = (parks[0].park_id, parks[0].token_enc)
        park_id, envelope = park
        token = apple.open_park(envelope, park_id)
        with db.social_scope() as social:
            attached = social.attach(user_id, subject, park_id, apple.seal_user(token, user_id))
        if attached:
            log.info("apple token attached")
        return attached
    except (TokenCipherError, ValueError) as exc:
        log.warning("apple token not attached: %s", type(exc).__name__)
        return False


def run_apple_parks(db, apple: Optional[AppleTokens], *, now: Optional[datetime] = None, limit: int = 100) -> dict:
    """Maintenance (AR-5, AR-6): revoke expired parked tokens with Apple, then delete them; a failed revoke
    keeps the record and backs off. Also drops expired pending links (their parks expire with them)."""
    now = now or utcnow()
    result = {"pruned_pending_links": 0, "revoked_parked_apple_tokens": 0, "pending_parked_apple_tokens": 0}
    with db.social_scope() as social:
        result["pruned_pending_links"] = social.prune_links(now)
        due = social.parks_due(now, limit)
    for park_id, envelope, attempts in due:
        try:
            if apple is None:
                raise AppleRevokeFailed("apple_not_configured")
            apple.revoke(apple.open_park(envelope, park_id))
            with db.social_scope() as social:
                social.park_revoked(park_id)
            result["revoked_parked_apple_tokens"] += 1
        except (AppleRevokeFailed, TokenCipherError, ValueError) as exc:
            log.warning("parked apple token revoke pending: %s", type(exc).__name__)
            with db.social_scope() as social:
                social.park_retry(park_id, now + timedelta(seconds=min(3600, 30 * 2 ** min(attempts, 7))))
            result["pending_parked_apple_tokens"] += 1
    return result

