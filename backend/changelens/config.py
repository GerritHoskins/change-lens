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
                        logto_jwks_url=env.get("CHANGELENS_LOGTO_JWKS_URL"))
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
                **auth,
            )
        except ValueError as exc:
            raise RuntimeError(str(exc)) from None
