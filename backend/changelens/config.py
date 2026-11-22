"""Settings read once from the environment. Stages never read config (03 §9.1 `pipeline`)."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

# The fixed local dev tenant behind the dev token, and the subject the dev token maps to. The user
# and owner membership for it come from `python -m changelens.db seed-dev` (I-8 S1); GUARD checks
# them like any other account.
DEV_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
DEV_SUBJECT = "dev:default"
AUTH_MODES = ("dev", "logto")
# Local dev defaults (I-8 S3). The running processes connect as the app role, which row-level security
# applies to; migrations connect as the owner role; `bootstrap-roles` connects as the compose superuser.
# Deployed configs set all three URLs and both role passwords in the environment.
DEFAULT_DATABASE_URL = "postgresql+psycopg://changelens_app:changelens-app-dev-only@127.0.0.1:55432/changelens"
DEFAULT_MIGRATION_DATABASE_URL = ("postgresql+psycopg://changelens_owner:changelens-owner-dev-only"
                                  "@127.0.0.1:55432/changelens")
DEFAULT_ADMIN_DATABASE_URL = "postgresql+psycopg://changelens:changelens@127.0.0.1:55432/changelens"
# What a deployment (logto mode) must set itself. The local defaults for these point at the compose
# database, MinIO and the fake model; a deployed process that fell back to one would look healthy and
# serve nothing real, so a missing one stops it at start.
DEPLOYED_REQUIRED = ("CHANGELENS_DATABASE_URL", "CHANGELENS_S3_ENDPOINT", "CHANGELENS_S3_ACCESS_KEY",
                     "CHANGELENS_S3_SECRET_KEY", "CHANGELENS_S3_BUCKET", "CHANGELENS_LLM")
# Only the api and retention may hold these (03 §6). The worker parses uploaded files, so in logto mode it
# stops at start when it finds one in its environment (LR-4).
NOT_FOR_THE_WORKER = ("CHANGELENS_LOGTO_M2M_APP_ID", "CHANGELENS_LOGTO_M2M_APP_SECRET", "CHANGELENS_RATE_LIMIT_KEY",
                      "CHANGELENS_SMTP_PASSWORD", "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY")
# The early-bird list's confirmation mail (double opt-in) and its removal links: what the api needs in logto
# mode to send the mail, to build its links and to check a removal link. A missing one stops the api at start
# (the rule L11 set); the port has a default (587, STARTTLS). The api alone reads them: retention sends no
# mail and starts without them (`from_env(mail=False)`), and the worker refuses the two credentials.
EARLY_BIRD_REQUIRED = ("CHANGELENS_SMTP_HOST", "CHANGELENS_SMTP_USER", "CHANGELENS_SMTP_PASSWORD",
                       "CHANGELENS_MAIL_FROM", "CHANGELENS_PUBLIC_API_URL", "CHANGELENS_LANDING_URL",
                       "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY")
UNSUBSCRIBE_KEY_MIN = 32  # characters; also checked by `changelens.early_bird_export`


def database_url_from_env() -> str:
    """The app role's URL, for the api, worker and retention processes."""
    return os.environ.get("CHANGELENS_DATABASE_URL", DEFAULT_DATABASE_URL)


def migration_database_url_from_env() -> str:
    """The owner role's URL, for Alembic and `changelens.db seed-dev` only; never a running process."""
    return os.environ.get("CHANGELENS_MIGRATION_DATABASE_URL", DEFAULT_MIGRATION_DATABASE_URL)


def admin_database_url_from_env() -> str:
    """A superuser URL for `changelens.db bootstrap-roles` and `stamp-baseline` only."""
    return os.environ.get("CHANGELENS_ADMIN_DATABASE_URL", DEFAULT_ADMIN_DATABASE_URL)


@dataclass(frozen=True)
class Limits:
    """Upload limits checked before anything is stored (AC-20 basics; full set in I-1)."""
    max_text_bytes: int = 512 * 1024
    max_text_words: int = 15_000
    max_pdf_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20
    max_label_chars: int = 100
    # Parse sandbox caps (03 §6 Upload validation). Text cap in characters (~5 MB).
    max_extracted_chars: int = 5_000_000
    max_render_pixels: int = 40_000_000  # visibility render; larger pages fail closed
    parse_wall_seconds: float = 60.0
    parse_cpu_seconds: int = 60
    parse_memory_mb: int = 512


@dataclass(frozen=True)
class Settings:
    database_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    # dev mode only: token -> IdP-style subject (e.g. "dev:default"). The subject still needs a
    # user and an active membership (GUARD, 03a P0); the token never names a tenant.
    dev_tokens: dict = field(default_factory=dict, repr=False)
    cost_ceiling_eur: Decimal = Decimal("1.50")
    fake_llm_cost_eur: Decimal = Decimal("0.01")
    job_max_attempts: int = 3
    job_lease_seconds: int = 300
    limits: Limits = Limits()
    llm_provider: str = "fake"  # fake | ionos (I-2)
    llm_model: str = "Qwen/Qwen3.5-397B-A17B"  # the only comparison model (06, 2026-10-31)
    ionos_env_file: Optional[str] = None  # file holding IONOS_API_TOKEN, read in place
    auth_mode: str = "dev"  # dev (local and tests only) | logto
    logto_issuer: Optional[str] = None
    logto_audience: Optional[str] = None  # the API resource indicator
    logto_jwks_url: Optional[str] = None
    # Logto Management API (I-8 S5): a machine-to-machine app that may delete users (account deletion).
    logto_management_endpoint: Optional[str] = None  # the Logto base URL, https
    logto_m2m_app_id: Optional[str] = None
    logto_m2m_app_secret: Optional[str] = field(default=None, repr=False)
    logto_management_resource: str = "https://default.logto.app/api"
    # Native Google and Apple sign-in (I-8 S4), logto mode only. Secrets are files named here (03 §6).
    google_client_id: Optional[str] = None  # the server (web) OAuth client the apps request codes for
    google_client_secret_file: Optional[str] = None
    google_redirect_uri: str = ""  # empty for codes from the native SDKs
    apple_client_id: Optional[str] = None  # the app's bundle ID (native codes)
    apple_team_id: Optional[str] = None
    apple_key_id: Optional[str] = None
    apple_private_key_file: Optional[str] = None  # the .p8 key
    apple_token_keys_file: Optional[str] = None  # keyring for stored Apple refresh tokens (AR-3)
    # Cost and abuse limits (I-8 S6; 06, 2026-11-13). Changeable through the environment, no release.
    tenant_monthly_spend_cap_eur: Decimal = Decimal("5")
    global_monthly_spend_cap_eur: Decimal = Decimal("50")  # the kill switch for new work
    rate_limit_account_per_minute: int = 60
    rate_limit_ip_per_minute: int = 20  # requests failing authentication, and POST /session
    signups_per_ip_per_day: int = 5
    trusted_proxies: tuple = ()  # proxy addresses whose X-Forwarded-For is believed
    rate_limit_key: str = field(default="changelens-dev-only-rate-limit-key-0000", repr=False)  # HMAC key
    # Per-account bounds on uploads and queued work (LR-10): one account must not keep the single worker busy
    # for everyone or fill the storage. A request over one is `429 account_limit_reached`.
    max_unparsed_versions: int = 8  # uploads the worker hasn't parsed yet; a comparison can add two
    max_unfinished_comparisons: int = 3  # waiting, queued or running
    max_stored_bytes: int = 1024 ** 3  # originals kept for the account
    # Upload requests that hold a body in memory at once in one api process; one account gets half of them.
    max_concurrent_uploads: int = 4
    # The privacy-policy version a usage-events consent answer must name (D-18 tier B). Changing it makes
    # every earlier answer read as unanswered, so the app asks again.
    consent_policy_version: str = "2026-11-13"
    # The early-bird list (docs/landing-page-handoff.md): `POST /early-bird` and its confirmation mail.
    early_bird_per_ip_per_day: int = 5  # sign-up requests per IP per UTC day
    early_bird_mails_per_address_per_day: int = 3  # confirmation mails to one address per UTC day
    early_bird_mails_per_hour: int = 30  # confirmation mails to all addresses together, per hour
    early_bird_mails_per_day: int = 200  # and per UTC day
    early_bird_mails_per_row: int = 5  # confirmation mails for one pending sign-up, over its whole life
    smtp_host: Optional[str] = None  # set = the SMTP sender; logto mode requires it (from_env)
    smtp_port: int = 587  # submission with STARTTLS
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = field(default=None, repr=False)
    mail_from: Optional[str] = None  # the confirmation mail's sender address
    public_api_url: str = ""  # this API's public origin, for the confirmation link
    landing_url: str = ""  # the landing page's origin: redirect target and the one allowed CORS origin
    # The HMAC key of the list's removal links (`api/early_bird_unsubscribe.py`). Its own key, not the
    # rate-limit key: replacing it ends every removal link already mailed.
    early_bird_unsubscribe_key: str = field(default="changelens-dev-only-unsubscribe-key-0000", repr=False)
    # The demo period (docs/demo-wall-handoff.md). The limit is comparisons per account for its lifetime;
    # 0 switches it off. The discount flag only switches a sentence on in the app (`discount_offered`);
    # it stays off until the legal review has answered. Neither is required anywhere.
    demo_comparison_limit: int = 3
    demo_feedback_discount: bool = False
    # The owner role's URL (I-8 S3): migrations only. The running processes use `database_url`.
    migration_database_url: Optional[str] = field(default=None, repr=False)
    # The worker's settings (LR-4): it checks no token and calls no sign-in service, so it holds none of their
    # settings, in any mode.
    worker: bool = False

    def __post_init__(self):
        if self.auth_mode not in AUTH_MODES:
            raise ValueError("auth_mode must be dev or logto")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.dev_tokens.items()):
            raise ValueError("dev_tokens maps token strings to subject strings")
        if self.worker and (self.logto_management_endpoint or self.logto_m2m_app_id or self.logto_m2m_app_secret
                            or self.google_client_id or self.apple_client_id):
            raise ValueError("the worker holds no Logto, Google or Apple settings")
        if self.auth_mode == "logto" and self.dev_tokens:
            raise ValueError("dev tokens are refused in logto mode")
        if self.auth_mode == "logto" and not self.worker:
            if not (self.logto_issuer and self.logto_audience and self.logto_jwks_url):
                raise ValueError("logto mode needs issuer, audience and JWKS URL")
            # Plain string checks: config imports no URL or network module (test_injection allow-list).
            url = self.logto_jwks_url
            authority = url[len("https://"):].split("/", 1)[0] if url.startswith("https://") else ""
            if not authority or "@" in authority or url != url.strip():
                raise ValueError("the Logto JWKS URL must be https")
        for cap in (self.tenant_monthly_spend_cap_eur, self.global_monthly_spend_cap_eur):
            if not isinstance(cap, Decimal) or not cap.is_finite() or cap < 0:
                raise ValueError("spend caps must be non-negative amounts")
        for limit in (self.rate_limit_account_per_minute, self.rate_limit_ip_per_minute, self.signups_per_ip_per_day,
                      self.early_bird_per_ip_per_day, self.early_bird_mails_per_address_per_day,
                      self.early_bird_mails_per_hour, self.early_bird_mails_per_day, self.early_bird_mails_per_row):
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                raise ValueError("rate limits must be positive integers")
        limit = self.demo_comparison_limit
        if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 1000:
            raise ValueError("the demo comparison limit must be 0 (off) to 1000")
        if not isinstance(self.demo_feedback_discount, bool):
            raise ValueError("the demo feedback discount setting must be true or false")
        if self.early_bird_mails_per_row > 100:
            raise ValueError("at most 100 confirmation mails per pending sign-up")
        if not isinstance(self.smtp_port, int) or isinstance(self.smtp_port, bool) or not 1 <= self.smtp_port <= 65535:
            raise ValueError("the SMTP port must be 1 to 65535")
        if self.worker and (self.smtp_host or self.smtp_user or self.smtp_password or self.mail_from):
            raise ValueError("the worker holds no mail settings")
        key = self.early_bird_unsubscribe_key
        if not isinstance(key, str) or len(key) < UNSUBSCRIBE_KEY_MIN:
            raise ValueError("the early-bird unsubscribe key needs at least 32 characters")
        if self.smtp_host is not None and not (_plain(self.smtp_host) and _plain(self.smtp_user)
                                               and self.smtp_password and _mail_address(self.mail_from)):
            raise ValueError("the SMTP sender needs host, user, password and a from-address")
        if self.auth_mode == "logto" and self.smtp_host is not None and not (self.public_api_url and self.landing_url):
            raise ValueError("the confirmation mail needs the public API URL and the landing URL")
        for url in (self.public_api_url, self.landing_url):
            if url and not _origin(url, https_only=self.auth_mode == "logto"):
                raise ValueError("the public API URL and the landing URL must be origins (scheme and host, no path)")
        bounds = (self.max_unparsed_versions, self.max_unfinished_comparisons, self.max_stored_bytes,
                  self.max_concurrent_uploads)
        if any(type(bound) is not int or bound < 1 for bound in bounds) or self.max_unparsed_versions < 2:
            raise ValueError("account bounds must be positive integers; one comparison can add two unparsed versions")
        version = self.consent_policy_version
        if not isinstance(version, str) or not 1 <= len(version) <= 32 or version != version.strip():
            raise ValueError("the consent policy version must be 1 to 32 characters")
        if len(self.rate_limit_key) < 32:
            raise ValueError("the rate-limit key needs at least 32 characters")
        object.__setattr__(self, "trusted_proxies", tuple(_ip(p) for p in self.trusted_proxies))
        if self.google_client_id and not self.google_client_secret_file:
            raise ValueError("Google sign-in needs a client secret file")
        if self.apple_client_id and not (self.apple_team_id and self.apple_key_id and self.apple_private_key_file
                                         and self.apple_token_keys_file):
            raise ValueError("Apple sign-in needs team ID, key ID, .p8 key file and token keyring file")
        if (self.google_client_id or self.apple_client_id) and self.auth_mode != "logto":
            raise ValueError("Google and Apple sign-in need logto mode")
        management = self.logto_management_endpoint
        if management is not None and (not management.startswith("https://") or management != management.strip()
                                       or not (self.logto_m2m_app_id and self.logto_m2m_app_secret)):
            raise ValueError("Logto management needs an https endpoint, app ID and secret")

    @classmethod
    def from_env(cls, worker: bool = False, mail: bool = True) -> "Settings":
        """`worker=True` reads the worker's settings: the same database, storage and model requirements, nothing
        about sign-in, and in logto mode no start when a credential it must not hold is set. `mail=False`
        (retention) reads no mail, link or removal-key setting and requires none: only the api sends mail."""
        env = os.environ
        mode = env.get("CHANGELENS_AUTH_MODE", "dev")
        auth: dict = {"auth_mode": mode, "worker": worker}
        if mode == "dev":
            # The dev token is never accepted by a deployed config (I-8 overview, decision 2).
            if env.get("CHANGELENS_ENV") != "local":
                raise RuntimeError("CHANGELENS_AUTH_MODE=dev requires CHANGELENS_ENV=local")
            token = env.get("CHANGELENS_DEV_TOKEN", "")
            if len(token) < 16:
                raise RuntimeError("CHANGELENS_DEV_TOKEN must be set (at least 16 characters)")
            auth["dev_tokens"] = {token: DEV_SUBJECT}
        elif mode == "logto":
            if env.get("CHANGELENS_DEV_TOKEN"):
                raise RuntimeError("CHANGELENS_DEV_TOKEN must not be set in logto mode")
            if worker:
                held = [name for name in NOT_FOR_THE_WORKER if env.get(name)]
                if held:
                    raise RuntimeError("the worker must not be given " + ", ".join(held))
            else:
                auth.update(_sign_in_from_env(env))
            # Names only in the message: the values are credentials.
            missing = [name for name in DEPLOYED_REQUIRED if not env.get(name, "").strip()]
            if missing:
                raise RuntimeError("logto mode needs " + ", ".join(missing))
            if env["CHANGELENS_LLM"].strip() == "fake":
                raise RuntimeError("CHANGELENS_LLM=fake is refused in logto mode")
        else:
            raise RuntimeError("CHANGELENS_AUTH_MODE must be dev or logto")
        try:
            return cls(
                database_url=database_url_from_env(),
                migration_database_url=migration_database_url_from_env(),
                s3_endpoint=env.get("CHANGELENS_S3_ENDPOINT", "http://127.0.0.1:59000"),
                s3_access_key=env.get("CHANGELENS_S3_ACCESS_KEY", "changelens"),
                # Defaults match backend/docker-compose.yml (local dev only).
                s3_secret_key=env.get("CHANGELENS_S3_SECRET_KEY", "changelens-dev-only"),
                s3_bucket=env.get("CHANGELENS_S3_BUCKET", "changelens-dev"),
                cost_ceiling_eur=Decimal(env.get("CHANGELENS_COST_CEILING_EUR", "1.50")),
                fake_llm_cost_eur=Decimal(env.get("CHANGELENS_FAKE_LLM_COST_EUR", "0.01")),
                llm_provider=env.get("CHANGELENS_LLM", "fake"),
                llm_model=env.get("CHANGELENS_LLM_MODEL", "Qwen/Qwen3.5-397B-A17B"),
                ionos_env_file=env.get("CHANGELENS_IONOS_ENV_FILE"),
                tenant_monthly_spend_cap_eur=Decimal(env.get("CHANGELENS_TENANT_SPEND_CAP_EUR", "5")),
                global_monthly_spend_cap_eur=Decimal(env.get("CHANGELENS_GLOBAL_SPEND_CAP_EUR", "50")),
                rate_limit_account_per_minute=int(env.get("CHANGELENS_RATE_LIMIT_ACCOUNT_PER_MINUTE", "60")),
                rate_limit_ip_per_minute=int(env.get("CHANGELENS_RATE_LIMIT_IP_PER_MINUTE", "20")),
                signups_per_ip_per_day=int(env.get("CHANGELENS_SIGNUPS_PER_IP_PER_DAY", "5")),
                max_unparsed_versions=int(env.get("CHANGELENS_MAX_UNPARSED_VERSIONS", "8")),
                max_unfinished_comparisons=int(env.get("CHANGELENS_MAX_UNFINISHED_COMPARISONS", "3")),
                max_stored_bytes=int(env.get("CHANGELENS_MAX_STORED_BYTES", str(1024 ** 3))),
                max_concurrent_uploads=int(env.get("CHANGELENS_MAX_CONCURRENT_UPLOADS", "4")),
                consent_policy_version=env.get("CHANGELENS_CONSENT_POLICY_VERSION", "2026-11-13"),
                trusted_proxies=tuple(p.strip() for p in env.get("CHANGELENS_TRUSTED_PROXIES", "").split(",") if p.strip()),
                early_bird_per_ip_per_day=int(env.get("CHANGELENS_EARLY_BIRD_PER_IP_PER_DAY", "5")),
                early_bird_mails_per_address_per_day=int(
                    env.get("CHANGELENS_EARLY_BIRD_MAILS_PER_ADDRESS_PER_DAY", "3")),
                early_bird_mails_per_hour=int(env.get("CHANGELENS_EARLY_BIRD_MAILS_PER_HOUR", "30")),
                early_bird_mails_per_day=int(env.get("CHANGELENS_EARLY_BIRD_MAILS_PER_DAY", "200")),
                early_bird_mails_per_row=int(env.get("CHANGELENS_EARLY_BIRD_MAILS_PER_ROW", "5")),
                demo_comparison_limit=int(env.get("CHANGELENS_DEMO_COMPARISON_LIMIT", "3")),
                demo_feedback_discount=_flag(env.get("CHANGELENS_DEMO_FEEDBACK_DISCOUNT", "false")),
                **(_early_bird_from_env(env, mode) if mail and not worker else {}),
                **auth,
            )
        except (ValueError, ArithmeticError) as exc:
            raise RuntimeError(str(exc)) from None


def _sign_in_from_env(env) -> dict:
    """What the api and retention need in logto mode and the worker never reads."""
    auth = dict(logto_issuer=env.get("CHANGELENS_LOGTO_ISSUER"),
                logto_audience=env.get("CHANGELENS_LOGTO_AUDIENCE"),
                logto_jwks_url=env.get("CHANGELENS_LOGTO_JWKS_URL"),
                logto_management_endpoint=env.get("CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT"),
                logto_m2m_app_id=env.get("CHANGELENS_LOGTO_M2M_APP_ID"),
                logto_m2m_app_secret=env.get("CHANGELENS_LOGTO_M2M_APP_SECRET"))
    for name in ("google_client_id", "google_client_secret_file", "google_redirect_uri", "apple_client_id",
                 "apple_team_id", "apple_key_id", "apple_private_key_file", "apple_token_keys_file"):
        if env.get("CHANGELENS_" + name.upper()):
            auth[name] = env["CHANGELENS_" + name.upper()]
    if env.get("CHANGELENS_LOGTO_MANAGEMENT_RESOURCE"):
        auth["logto_management_resource"] = env["CHANGELENS_LOGTO_MANAGEMENT_RESOURCE"]
    # A deployment keys its rate-limit counters with its own secret (I-8 S6).
    if len(env.get("CHANGELENS_RATE_LIMIT_KEY", "")) < 32:
        raise RuntimeError("logto mode needs CHANGELENS_RATE_LIMIT_KEY (at least 32 characters)")
    auth["rate_limit_key"] = env["CHANGELENS_RATE_LIMIT_KEY"]
    # Account deletion must reach Logto (I-8 S5): a deployment without it doesn't start.
    if not auth["logto_management_endpoint"]:
        raise RuntimeError("logto mode needs CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT, _M2M_APP_ID and _M2M_APP_SECRET")
    return auth


def _early_bird_from_env(env, mode: str) -> dict:
    """The early-bird list's mail, link and removal-key settings, for the api; retention and the worker never
    read them. In logto mode a missing one stops the api: a sign-up form that answers 202 and sends no
    mail would look healthy and confirm nobody, and removal links signed with a development key could be
    forged. Dev mode sends nothing (the recording sender), so all are optional."""
    if mode == "logto":
        # Names only in the message: one of the values is a credential.
        missing = [name for name in EARLY_BIRD_REQUIRED if not env.get(name, "").strip()]
        if missing:
            raise RuntimeError("logto mode needs " + ", ".join(missing))
    values = {name: env.get("CHANGELENS_" + name.upper(), "").strip()
              for name in ("smtp_host", "smtp_user", "mail_from", "public_api_url", "landing_url")}
    mail = {"public_api_url": values.pop("public_api_url").rstrip("/"),
            "landing_url": values.pop("landing_url").rstrip("/"),
            "smtp_port": int(env.get("CHANGELENS_SMTP_PORT", "587"))}
    if env.get("CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY"):
        mail["early_bird_unsubscribe_key"] = env["CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY"]
    if values["smtp_host"]:
        mail.update(values, smtp_password=env.get("CHANGELENS_SMTP_PASSWORD", ""))
    return mail


def _flag(value: str) -> bool:
    """`true` or `false` (also 1/0, on/off, yes/no); anything else stops the process at start."""
    word = value.strip().lower()
    if word in ("true", "1", "on", "yes"):
        return True
    if word in ("false", "0", "off", "no", ""):
        return False
    raise ValueError("a true/false setting has another value")


def _plain(value) -> bool:
    """A non-empty setting with no whitespace or control character (a host or user name)."""
    return isinstance(value, str) and bool(value) and all(33 <= ord(c) < 127 for c in value)


def _mail_address(value) -> bool:
    return _plain(value) and value.count("@") == 1 and "" not in value.split("@") and not set(value) & set("<>,;\"")


def _origin(url: str, https_only: bool) -> bool:
    """`scheme://host[:port]` and nothing else. Plain string checks: config imports no URL module."""
    scheme, sep, authority = url.partition("://")
    if not sep or scheme not in (("https",) if https_only else ("https", "http")):
        return False
    return _plain(authority) and not set(authority) & set("/@?#\\") and not authority.startswith((".", ":"))


def _ip(value) -> str:
    import ipaddress  # stdlib parsing only; no network access
    return str(ipaddress.ip_address(str(value).strip()))
