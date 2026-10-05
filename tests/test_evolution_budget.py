"""An exhausted allowance and a competing supervisor must never launch work."""
import fcntl
import json
from types import SimpleNamespace

import pytest

from scripts import run_evolution


def test_exhausted_resume_never_checks_auth_or_starts_engine(tmp_path, monkeypatch):
    checkpoint = {"elapsed_search_seconds": 3600, "status": "budget_exhausted"}
    (tmp_path / "budget_checkpoint.json").write_text(json.dumps(checkpoint))

    def forbidden():
        raise AssertionError("Exhausted allowance must not reach authentication")

    monkeypatch.setattr(run_evolution, "check_subscription", forbidden)
    args = SimpleNamespace(run_dir=tmp_path, resume=True, budget_minutes=60)
    assert run_evolution.supervise(args) == 0
    assert json.loads((tmp_path / "budget_checkpoint.json").read_text()) == checkpoint


def test_filesystem_lock_prevents_second_supervisor_across_pid_namespaces(tmp_path):
    with (tmp_path / "supervisor.lock").open("a+") as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        args = SimpleNamespace(run_dir=tmp_path, resume=True, budget_minutes=60)
        with pytest.raises(RuntimeError, match="already owns"):
            run_evolution.supervise(args)
