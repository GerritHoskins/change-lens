"""The maintenance command requires --apply and never bootstraps stores during preview."""
from types import SimpleNamespace

import pytest

from changelens.retention import __main__ as cli


@pytest.mark.parametrize("apply", [False, True])
def test_one_pass_is_read_only_unless_explicitly_applied(monkeypatch, capsys, apply):
    calls = []
    engine = SimpleNamespace(dispose=lambda: calls.append("dispose"))
    db = SimpleNamespace(engine=engine, _intent_engine=engine)
    settings = SimpleNamespace(database_url="synthetic", s3_endpoint="synthetic", s3_access_key="synthetic",
                               s3_secret_key="synthetic", s3_bucket="synthetic")
    monkeypatch.setattr(cli.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(cli, "Database", lambda url: db)
    monkeypatch.setattr(cli, "S3ObjectStore", lambda *args: object())
    monkeypatch.setattr(cli, "configure_logging", lambda: None)

    def maintain(database, store, **kwargs):
        assert database is db
        calls.append(kwargs)
        return {"execute": kwargs["execute"], "candidate_projects": 3}

    monkeypatch.setattr(cli, "run_maintenance", maintain)
    assert cli.main(["--once", "--limit", "7"] + (["--apply"] if apply else [])) == 0
    assert calls == [{"limit": 7, "execute": apply}, "dispose", "dispose"]
    assert '"candidate_projects": 3' in capsys.readouterr().out


@pytest.mark.parametrize("args", [["--limit", "0"], ["--interval-seconds", "-1"]])
def test_bad_limits_are_rejected_before_accessing_configuration(monkeypatch, args):
    monkeypatch.setattr(cli.Settings, "from_env", lambda: pytest.fail("must reject before configuration"))
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
