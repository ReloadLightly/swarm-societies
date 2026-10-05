"""Campaign control-flow fixtures never invoke Shinka or a model provider."""
import json
from pathlib import Path
import signal
import sys

import pytest

from scripts import run_consumption_study as campaign
from tests.test_evolution_budget import make_run_args


def make_plan(tmp_path, postprocess=True):
    runs = []
    for index, condition in enumerate(["coevolution", "fixed_institution"]):
        args = make_run_args(tmp_path / f"arm-{index}")
        runs.append({"id": condition, "condition": condition, "replicate": 0,
                     "budget_minutes": .001, "search_seed": 100 + index,
                     **{key: str(getattr(args, key)) for key in campaign.PATH_FIELDS}})
    plan = {"schema_version": 1, "runs": runs}
    if postprocess:
        plan["postprocess_command"] = [sys.executable, "-c",
            "from pathlib import Path;import sys;p=Path(sys.argv[1]);p.write_text(p.read_text()+'done\\n' if p.exists() else 'done\\n')",
            str(tmp_path / "postprocessed.txt")]
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(plan))
    return path


FIXTURE_RUNNER = """
import json,sys
from pathlib import Path
directory=Path(sys.argv[1]);budget=float(sys.argv[3])*60
with Path(sys.argv[4]).open('a') as f:f.write(sys.argv[2]+'\\n')
(directory/'budget_checkpoint.json').write_text(json.dumps({'status':'budget_exhausted','budget_seconds':budget,'elapsed_search_seconds':budget,'remaining_search_seconds':0}))
"""


def test_queue_and_postprocessing_complete_once_across_resume(tmp_path, monkeypatch):
    plan_path = make_plan(tmp_path)
    order = tmp_path / "order.txt"
    monkeypatch.setattr(campaign, "runner_command", lambda run: [
        sys.executable, "-c", FIXTURE_RUNNER, run["run_dir"], run["id"],
        str(run["budget_minutes"]), str(order),
    ])
    assert campaign.run_campaign(plan_path) == 0
    assert campaign.run_campaign(plan_path, resume=True) == 0
    assert order.read_text().splitlines() == ["coevolution", "fixed_institution"]
    assert (tmp_path / "postprocessed.txt").read_text().splitlines() == ["done"]
    state = json.loads((tmp_path / "campaign_checkpoint.json").read_text())
    assert state["status"] == "completed"
    assert state["elapsed_search_seconds"] == pytest.approx(.12)
    assert state["postprocess"]["status"] == "completed"


def test_resume_rejects_campaign_budget_growth_before_subprocess(tmp_path, monkeypatch):
    path = make_plan(tmp_path)
    plan = campaign.load_plan(path)
    state = campaign.initialize_checkpoint(plan, None)
    changed = json.loads(path.read_text()); changed["runs"][0]["budget_minutes"] *= 2
    path.write_text(json.dumps(changed))
    with pytest.raises(RuntimeError, match="plan changed"):
        campaign.initialize_checkpoint(campaign.load_plan(path), state)


def test_failure_stops_queue_without_postprocessing(tmp_path, monkeypatch):
    path = make_plan(tmp_path)
    monkeypatch.setattr(campaign, "runner_command", lambda run: [sys.executable, "-c", "raise SystemExit(3)"])
    assert campaign.run_campaign(path) == 1
    state = json.loads((tmp_path / "campaign_checkpoint.json").read_text())
    assert state["status"] == "failed"
    assert state["runs"][1]["status"] == "pending"
    assert not (tmp_path / "postprocessed.txt").exists()


def test_signal_propagates_to_supervisor_and_keeps_next_arm_pending(tmp_path, monkeypatch):
    path = make_plan(tmp_path)
    plan = campaign.load_plan(path)
    handlers, calls = {}, []
    monkeypatch.setattr(campaign.signal, "signal", lambda sig, handler: handlers.setdefault(sig, handler))

    class FixtureProcess:
        pid = 123456789
        returncode = None
        signaled = False

        def __init__(self, command, **kwargs):
            self.directory = Path(plan["runs"][0]["run_dir"])
            self.write("running")

        def write(self, status):
            (self.directory / "budget_checkpoint.json").write_text(json.dumps({
                "status": status, "budget_seconds": .06, "elapsed_search_seconds": .02,
                "remaining_search_seconds": .04,
            }))

        def poll(self):
            if not self.signaled:
                self.signaled = True
                handlers[signal.SIGTERM](signal.SIGTERM, None)
            return self.returncode

        def terminate(self):
            calls.append("terminated")
            self.write("interrupted")
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(campaign.subprocess, "Popen", FixtureProcess)
    assert campaign.run_campaign(path) == 130
    state = json.loads((tmp_path / "campaign_checkpoint.json").read_text())
    assert calls == ["terminated"]
    assert state["status"] == "interrupted"
    assert state["runs"][1]["status"] == "pending"
    assert state["postprocess"]["status"] == "pending"


def test_relative_paths_resolve_against_plan_directory(tmp_path):
    path = make_plan(tmp_path, postprocess=False)
    raw = json.loads(path.read_text())
    for run in raw["runs"]:
        for key in campaign.PATH_FIELDS:
            run[key] = str(Path(run[key]).relative_to(tmp_path))
    path.write_text(json.dumps(raw))
    plan = campaign.load_plan(path)
    assert Path(plan["runs"][0]["evaluator"]).is_absolute()
    assert Path(plan["runs"][0]["evaluator"]).exists()
