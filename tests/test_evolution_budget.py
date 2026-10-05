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


def make_run_args(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    paths = {}
    for key, suffix in [("evaluator", ".py"), ("task_prompt", ".md"), ("initial_program", ".py")]:
        paths[key] = tmp_path / (key + suffix)
        paths[key].write_text("initial content\n")
    paths["context"] = tmp_path / "context.json"
    paths["context"].write_text(json.dumps({
        "config": {"ticks": 60}, "condition": "coevolution", "search_seeds": [101],
        "initial_members": [[str(paths["initial_program"])]],
        "members": [[str(paths["initial_program"])]], "institutions": [],
        "evaluations": [], "accepted_member_updates": 0, "accepted_institution_updates": 0,
    }))
    return SimpleNamespace(run_dir=tmp_path, resume=False, budget_minutes=30,
                           search_seed=17, max_generations=100000, **paths)


def test_resume_cannot_grow_even_an_exhausted_budget(tmp_path, monkeypatch):
    (tmp_path / "budget_checkpoint.json").write_text(json.dumps({
        "status": "budget_exhausted", "budget_seconds": 1800, "elapsed_search_seconds": 1800,
    }))
    monkeypatch.setattr(run_evolution, "check_subscription", lambda: pytest.fail("No auth on rejected budget"))
    with pytest.raises(RuntimeError, match="cannot change"):
        run_evolution.supervise(SimpleNamespace(run_dir=tmp_path, resume=True, budget_minutes=60))


def test_mutable_ecological_updates_do_not_invalidate_resume(tmp_path):
    args = make_run_args(tmp_path)
    first = run_evolution.freeze_run_plan(args, {}, 1800)
    context = json.loads(args.context.read_text())
    context.update(members=[["a new inherited program"]], evaluations=[{"accepted": True}],
                   accepted_member_updates=1)
    args.context.write_text(json.dumps(context))
    resumed = run_evolution.freeze_run_plan(args, {"elapsed_search_seconds": 11}, 1800)
    assert resumed == first
    assert run_evolution.file_sha256(args.context) != first["initial_context_sha256"]


@pytest.mark.parametrize("changed", ["evaluator", "task_prompt", "initial_program", "config", "budget", "seed"])
def test_resume_rejects_changed_science_and_allocation(tmp_path, changed):
    args = make_run_args(tmp_path)
    run_evolution.freeze_run_plan(args, {}, 1800)
    budget = 1800
    if changed in {"evaluator", "task_prompt", "initial_program"}:
        getattr(args, changed).write_text("changed\n")
    elif changed == "config":
        context = json.loads(args.context.read_text()); context["config"]["ticks"] = 99
        args.context.write_text(json.dumps(context))
    elif changed == "seed":
        args.search_seed = 18
    else:
        budget = 3600
    with pytest.raises(RuntimeError, match="mismatch"):
        run_evolution.freeze_run_plan(args, {"elapsed_search_seconds": 11}, budget)


def test_evaluator_and_seed_are_forwarded_to_real_worker(tmp_path):
    args = make_run_args(tmp_path)
    command = run_evolution.worker_command(args)
    assert command[command.index("--evaluator") + 1] == str(args.evaluator)
    assert command[command.index("--search-seed") + 1] == "17"
