"""Settings read once from the environment. Stages never read config (03 §9.1 `pipeline`)."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

# The single fixed dev tenant behind the dev token. I-8 replaces this with Logto memberships.
DEV_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


@dataclass(frozen=True)
class Limits:
    """Upload limits checked before anything is stored (AC-20 basics; full set in I-1)."""
    max_text_bytes: int = 512 * 1024
    max_text_words: int = 15_000
    max_pdf_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 20
    max_label_chars: int = 100


@dataclass(frozen=True)
class Settings:
    database_url: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    # token -> tenant. Production config has exactly one entry; tests may add a second tenant.
    dev_tokens: dict = field(default_factory=dict)
    cost_ceiling_eur: Decimal = Decimal("1.50")
    fake_llm_cost_eur: Decimal = Decimal("0.01")
    job_max_attempts: int = 3
    job_lease_seconds: int = 300
    limits: Limits = Limits()

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        token = env.get("CHANGELENS_DEV_TOKEN", "")
        if len(token) < 16:
            raise RuntimeError("CHANGELENS_DEV_TOKEN must be set (at least 16 characters)")
        return cls(
            database_url=env.get("CHANGELENS_DATABASE_URL",
                                 "postgresql+psycopg://changelens:changelens@127.0.0.1:55432/changelens"),
            s3_endpoint=env.get("CHANGELENS_S3_ENDPOINT", "http://127.0.0.1:59000"),
            s3_access_key=env.get("CHANGELENS_S3_ACCESS_KEY", "changelens"),
            # Defaults match backend/docker-compose.yml (local dev only).
            s3_secret_key=env.get("CHANGELENS_S3_SECRET_KEY", "changelens-dev-only"),
            s3_bucket=env.get("CHANGELENS_S3_BUCKET", "changelens-dev"),
            dev_tokens={token: DEV_TENANT_ID},
            cost_ceiling_eur=Decimal(env.get("CHANGELENS_COST_CEILING_EUR", "1.50")),
            fake_llm_cost_eur=Decimal(env.get("CHANGELENS_FAKE_LLM_COST_EUR", "0.01")),
        )
