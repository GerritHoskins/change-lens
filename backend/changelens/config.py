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
    # Cost and abuse limits (I-8 S6; 06, 2026-11-13). Changeable through the environment, no release.
    tenant_monthly_spend_cap_eur: Decimal = Decimal("5")
    global_monthly_spend_cap_eur: Decimal = Decimal("50")  # the kill switch for new work
    rate_limit_account_per_minute: int = 60
    rate_limit_ip_per_minute: int = 20  # requests failing authentication, and POST /session
    signups_per_ip_per_day: int = 5
    trusted_proxies: tuple = ()  # proxy addresses whose X-Forwarded-For is believed
    rate_limit_key: str = field(default="changelens-dev-only-rate-limit-key-0000", repr=False)  # HMAC key
    # The owner role's URL (I-8 S3): migrations only. The running processes use `database_url`.
    migration_database_url: Optional[str] = field(default=None, repr=False)

    def __post_init__(self):
        if self.auth_mode not in AUTH_MODES:
            raise ValueError("auth_mode must be dev or logto")
        if any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.dev_tokens.items()):
            raise ValueError("dev_tokens maps token strings to subject strings")
        if self.auth_mode == "logto":
            if not (self.logto_issuer and self.logto_audience and self.logto_jwks_url):
                raise ValueError("logto mode needs issuer, audience and JWKS URL")
            # Plain string checks: config imports no URL or network module (test_injection allow-list).
            url = self.logto_jwks_url
            authority = url[len("https://"):].split("/", 1)[0] if url.startswith("https://") else ""
            if not authority or "@" in authority or url != url.strip():
                raise ValueError("the Logto JWKS URL must be https")
            if self.dev_tokens:
                raise ValueError("dev tokens are refused in logto mode")
        for cap in (self.tenant_monthly_spend_cap_eur, self.global_monthly_spend_cap_eur):
            if not isinstance(cap, Decimal) or not cap.is_finite() or cap < 0:
                raise ValueError("spend caps must be non-negative amounts")
        for limit in (self.rate_limit_account_per_minute, self.rate_limit_ip_per_minute, self.signups_per_ip_per_day):
            if not isinstance(limit, int) or limit < 1:
                raise ValueError("rate limits must be positive integers")
        if len(self.rate_limit_key) < 32:
            raise ValueError("the rate-limit key needs at least 32 characters")
        object.__setattr__(self, "trusted_proxies", tuple(_ip(p) for p in self.trusted_proxies))
        management = self.logto_management_endpoint
        if management is not None and (not management.startswith("https://") or management != management.strip()
                                       or not (self.logto_m2m_app_id and self.logto_m2m_app_secret)):
            raise ValueError("Logto management needs an https endpoint, app ID and secret")

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        mode = env.get("CHANGELENS_AUTH_MODE", "dev")
        auth: dict = {"auth_mode": mode}
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
            auth.update(logto_issuer=env.get("CHANGELENS_LOGTO_ISSUER"),
                        logto_audience=env.get("CHANGELENS_LOGTO_AUDIENCE"),
                        logto_jwks_url=env.get("CHANGELENS_LOGTO_JWKS_URL"),
                        logto_management_endpoint=env.get("CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT"),
                        logto_m2m_app_id=env.get("CHANGELENS_LOGTO_M2M_APP_ID"),
                        logto_m2m_app_secret=env.get("CHANGELENS_LOGTO_M2M_APP_SECRET"))
            if env.get("CHANGELENS_LOGTO_MANAGEMENT_RESOURCE"):
                auth["logto_management_resource"] = env["CHANGELENS_LOGTO_MANAGEMENT_RESOURCE"]
            # A deployment keys its rate-limit counters with its own secret (I-8 S6).
            if len(env.get("CHANGELENS_RATE_LIMIT_KEY", "")) < 32:
                raise RuntimeError("logto mode needs CHANGELENS_RATE_LIMIT_KEY (at least 32 characters)")
            auth["rate_limit_key"] = env["CHANGELENS_RATE_LIMIT_KEY"]
            # Account deletion must reach Logto (I-8 S5): a deployment without it doesn't start.
            if not auth["logto_management_endpoint"]:
                raise RuntimeError("logto mode needs CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT, _M2M_APP_ID and _M2M_APP_SECRET")
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
                trusted_proxies=tuple(p.strip() for p in env.get("CHANGELENS_TRUSTED_PROXIES", "").split(",") if p.strip()),
                **auth,
            )
        except (ValueError, ArithmeticError) as exc:
            raise RuntimeError(str(exc)) from None


def _ip(value) -> str:
    import ipaddress  # stdlib parsing only; no network access
    return str(ipaddress.ip_address(str(value).strip()))
