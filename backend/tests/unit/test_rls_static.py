"""Static checks for I-8 S3 with no services: the RLS migration's table list and retention window, and
the role-password rules of `changelens.db bootstrap-roles`. The catalog itself is checked in
tests/integration/test_rls_db.py."""
import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest

from changelens.config import DEFAULT_DATABASE_URL, DEFAULT_MIGRATION_DATABASE_URL, Settings
from changelens.db import APP_ROLE, DEV_PASSWORDS, OWNER_ROLE, role_passwords
from changelens.domain.models import Base
from changelens.domain.retention import RETENTION

MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0003_rls.py"


def _migration():
    spec = importlib.util.spec_from_file_location("rls_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_covers_every_model_with_tenant_id():
    with_tenant = {t.name for t in Base.metadata.tables.values() if "tenant_id" in t.c}
    assert set(_migration().TENANT_TABLES) == with_tenant
    assert {t.name for t in Base.metadata.tables.values()} - with_tenant == {"users"}


def test_the_maintenance_function_uses_the_retention_window():
    assert timedelta(days=_migration().RETENTION_DAYS) == RETENTION


def test_role_passwords_come_from_the_environment_outside_local():
    with pytest.raises(RuntimeError):
        role_passwords({})
    with pytest.raises(RuntimeError):
        role_passwords({"CHANGELENS_OWNER_DB_PASSWORD": "short", "CHANGELENS_APP_DB_PASSWORD": "x" * 20})
    given = {"CHANGELENS_OWNER_DB_PASSWORD": "o" * 20, "CHANGELENS_APP_DB_PASSWORD": "a" * 20}
    assert role_passwords(given) == {OWNER_ROLE: "o" * 20, APP_ROLE: "a" * 20}
    assert role_passwords({"CHANGELENS_ENV": "local"}) == DEV_PASSWORDS


def test_processes_default_to_the_app_role_and_migrations_to_the_owner(monkeypatch):
    assert "//changelens_app:" in DEFAULT_DATABASE_URL and "//changelens_owner:" in DEFAULT_MIGRATION_DATABASE_URL
    monkeypatch.setenv("CHANGELENS_ENV", "local")
    monkeypatch.setenv("CHANGELENS_DEV_TOKEN", "t" * 20)
    monkeypatch.delenv("CHANGELENS_DATABASE_URL", raising=False)
    monkeypatch.setenv("CHANGELENS_MIGRATION_DATABASE_URL", "postgresql+psycopg://changelens_owner:pw@h/db")
    settings = Settings.from_env()
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.migration_database_url.endswith("@h/db") and "pw" not in repr(settings)
