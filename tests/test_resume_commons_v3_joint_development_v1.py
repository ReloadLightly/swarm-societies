"""Recovery engineering fixtures; no A2 scientific episode is executed."""
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import replace
import hashlib
from types import SimpleNamespace

import pytest

from scripts import resume_commons_v3_joint_development_v1 as resume


def record(job):
    dev = resume.dev
    state = dev.worlds.initialize(job["condition"], job["need"], job["seed"])
    state = replace(state, config=replace(state.config, max_messages=4))
    initial = dev.engine.snapshot(state)
    pairs = [[agent.id, patch.id] for agent in state.agents for patch in state.patches]
    return {
        "job": deepcopy(job), "version": dev.VERSION, "horizon": 512,
        "rate_known": False, "rate_prior": dict(dev.RATE_PRIOR),
        "initial_snapshot": initial,
        "initial_physical_sha256": dev.physical_initial_digest(initial),
        "final_snapshot": dev.engine.snapshot(replace(state, tick=512)),
        "trajectory_sha256": "0" * 64, "weather_sha256": "1" * 64,
        "final_policy_memory_sha256": ["2" * 64] * 24,
        "final_pool_memory_sha256": "3" * 64 if job["arm"] == "R-pool" else None,
        "ticks": [{**dict.fromkeys(resume.MATERIAL_KEYS, 0), "tick": tick} for tick in range(1, 513)],
        "belief_ticks": [{**dict.fromkeys(resume.BELIEF_KEYS, 0), "tick": tick} for tick in range(513)],
        "belief_pair_columns": list(dev.PAIR_COLUMNS),
        "belief_checkpoints": [{"tick": tick, "pairs": [pair + [0] * 7 for pair in pairs]}
                               for tick in dev.BELIEF_CHECKPOINTS],
        "agents": [{"id": agent.id} for agent in state.agents],
        "first_within10_columns": ["agent", "site", "first_tick_or_null"],
        "first_within10": [pair + [None] for pair in pairs],
        "summary": dict.fromkeys(resume.SUMMARY_KEYS, .8),
    }


class ImmediateExecutor:
    """Futures are completed cheaply; tests control their delivery order."""
    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def submit(self, function, job):
        future = Future()
        try:
            future.set_result(function(job))
        except Exception as error:
            future.set_exception(error)
        return future


def immediate(monkeypatch):
    monkeypatch.setattr(resume, "ProcessPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(resume.dev, "run_episode", record)


def test_out_of_order_completion_saves_immediately_but_returns_original_order(monkeypatch, tmp_path):
    immediate(monkeypatch)
    jobs = resume.dev.fallback_jobs()[:3]

    def delivered(futures):
        futures = list(futures)
        yield futures[2]
        # The slow first job has not been yielded; the third is already durable.
        assert resume.dev.base._path(tmp_path, jobs[2]).is_file()
        assert not resume.dev.base._path(tmp_path, jobs[0]).exists()
        yield futures[0]
        assert resume.dev.base._path(tmp_path, jobs[0]).is_file()
        yield futures[1]

    monkeypatch.setattr(resume, "as_completed", delivered)
    rows = resume._complete_missing(tmp_path, jobs, [None] * 3, 2)
    assert [row["job"] for row in rows] == jobs
    assert [resume.read_case(resume.dev.base._path(tmp_path, job)) for job in jobs] == rows


@pytest.mark.parametrize("failed_first", [False, True])
def test_worker_failure_preserves_successes_before_and_after_failure(monkeypatch, tmp_path, failed_first):
    immediate(monkeypatch)
    jobs = resume.dev.fallback_jobs()[:2]

    def worker(job):
        if job == jobs[0]:
            raise RuntimeError("interrupted fixture")
        return record(job)

    monkeypatch.setattr(resume.dev, "run_episode", worker)
    monkeypatch.setattr(resume, "as_completed", lambda futures: iter(futures) if failed_first else reversed(list(futures)))
    with pytest.raises(RuntimeError, match="interrupted fixture"):
        resume._complete_missing(tmp_path, jobs, [None] * 2, 2)
    assert resume.read_case(resume.dev.base._path(tmp_path, jobs[1])) == record(jobs[1])
    assert not resume.dev.base._path(tmp_path, jobs[0]).exists()


def test_failure_cancels_queued_work_and_drains_success_without_overwriting(monkeypatch, tmp_path):
    jobs = resume.dev.fallback_jobs()[:3]
    futures = []

    class QueuedExecutor(ImmediateExecutor):
        def submit(self, function, job):
            future = Future()
            if not futures:
                future.set_exception(RuntimeError("fixture failure"))
            elif len(futures) == 1:
                future.set_result(record(job))
            futures.append(future)
            return future

    monkeypatch.setattr(resume, "ProcessPoolExecutor", QueuedExecutor)
    monkeypatch.setattr(resume, "as_completed", iter)
    with pytest.raises(RuntimeError, match="fixture failure"):
        resume._complete_missing(tmp_path, jobs, [None] * 3, 2)
    assert futures[2].cancelled()
    assert resume.dev.base._path(tmp_path, jobs[1]).is_file()
    assert not resume.dev.base._path(tmp_path, jobs[2]).exists()


def test_conflicting_file_appearing_during_execution_is_never_overwritten(monkeypatch, tmp_path):
    immediate(monkeypatch)
    job = resume.dev.fallback_jobs()[0]
    path = resume.dev.base._path(tmp_path, job)
    saved = record(job)
    saved["summary"]["share_of_need"] = .1
    resume._save_record(path, saved)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="existing case differs"):
        resume._complete_missing(tmp_path, [job], [None], 1)
    assert path.read_bytes() == before


def test_preserved_record_is_not_submitted_or_overwritten(monkeypatch, tmp_path):
    immediate(monkeypatch)
    jobs = resume.dev.fallback_jobs()[:2]
    saved = record(jobs[0])
    path = resume.dev.base._path(tmp_path, jobs[0])
    resume._save_record(path, saved)
    before = path.read_bytes()
    submitted = []

    def worker(job):
        submitted.append(job)
        return record(job)

    monkeypatch.setattr(resume.dev, "run_episode", worker)
    rows = resume._complete_missing(tmp_path, jobs, [saved, None], 2)
    assert submitted == [jobs[1]] and path.read_bytes() == before
    assert [row["job"] for row in rows] == jobs


@pytest.mark.parametrize("damage", ["job", "prior", "horizon", "terminal", "material",
                                   "belief", "checkpoint", "pairs", "agents", "memory", "summary",
                                   "material_field", "belief_field", "nonheadline_summary"])
def test_partial_or_mismatched_records_are_rejected(damage):
    job = resume.dev.fallback_jobs()[0]
    row = record(job)
    if damage == "job":
        row["job"]["q"] = .5
    elif damage == "prior":
        row["rate_prior"]["high"] = .96
    elif damage == "horizon":
        row["horizon"] = 511
    elif damage == "terminal":
        row["final_snapshot"]["state"]["tick"] = 511
    elif damage in ("material", "belief", "checkpoint"):
        row[{"material": "ticks", "belief": "belief_ticks", "checkpoint": "belief_checkpoints"}[damage]].pop()
    elif damage == "pairs":
        row["belief_checkpoints"][-1]["pairs"].pop()
    elif damage == "agents":
        row["agents"].pop()
    elif damage == "memory":
        row["final_policy_memory_sha256"].pop()
    elif damage == "material_field":
        row["ticks"][-1].pop("consumption")
    elif damage == "belief_field":
        row["belief_ticks"][-1].pop("seen_only_absolute_log_error")
    elif damage == "nonheadline_summary":
        row["summary"].pop("agent_consumption_share_sd")
    else:
        row["summary"].pop("share_of_need")
    with pytest.raises(ValueError, match="incomplete or mismatched"):
        resume._validate_record(row, job)


def test_published_inventory_hashes_and_parameters_checked_before_preservation(monkeypatch, tmp_path):
    jobs = resume.dev.fallback_jobs()
    path = resume.dev.base._path(tmp_path, jobs[0])
    row = record(jobs[0])
    resume._save_record(path, row)
    published = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
    monkeypatch.setattr(resume, "_published_cases", lambda commit: published)
    assert resume._load_saved(tmp_path, jobs, "fixture")[0] == row
    published[path.name] = "0" * 64
    with pytest.raises(ValueError, match="published saved record differs"):
        resume._load_saved(tmp_path, jobs, "fixture")
    published.clear()
    with pytest.raises(ValueError, match="inventory differs"):
        resume._load_saved(tmp_path, jobs, "fixture")
    path.unlink()
    published[path.name] = "0" * 64
    with pytest.raises(ValueError, match="inventory differs"):
        resume._load_saved(tmp_path, jobs, "fixture")


def test_git_anchor_uses_pinned_published_blobs(monkeypatch):
    commit = "a" * 40
    name = resume.dev.FALLBACK_ROOT + "/cases/test.json.gz"
    calls = []

    def git(*args):
        calls.append(args)
        return (name + "\n").encode() if args[0] == "ls-tree" else b"raw case" if args[0] == "show" else b""

    monkeypatch.setattr(resume, "_git", git)
    assert resume._published_cases(commit) == {"test.json.gz": hashlib.sha256(b"raw case").hexdigest()}
    assert ("merge-base", "--is-ancestor", commit, "refs/remotes/origin/main") in calls
    assert ("show", commit + ":" + name) in calls
    with pytest.raises(ValueError, match="full reviewed published commit"):
        resume._published_cases("HEAD")


def test_completed_bank_and_failed_prerequisites_submit_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(resume, "_assert_no_active_runner", lambda: None)
    monkeypatch.setattr(resume, "_load_saved", lambda *args: [None] * 32)
    monkeypatch.setattr(resume, "_complete_missing", lambda *args: pytest.fail("submitted before prerequisites"))

    def blocked(*args):
        raise ValueError("G2 has not passed")

    monkeypatch.setattr(resume.dev, "_load_prerequisites", blocked)
    with pytest.raises(ValueError, match="G2"):
        resume.run(tmp_path, published_commit="fixture")
    (tmp_path / "summary.json").write_text("{}")
    with pytest.raises(ValueError, match="completed fallback"):
        resume.run(tmp_path, published_commit="fixture")


def test_run_preserves_fixed_32_job_order_and_existing_summary_format(monkeypatch, tmp_path):
    jobs = resume.dev.fallback_jobs()
    seen = []
    monkeypatch.setattr(resume, "_assert_no_active_runner", lambda: None)
    monkeypatch.setattr(resume, "_load_saved", lambda *args: [None] * 32)
    monkeypatch.setattr(resume.dev, "_load_prerequisites", lambda *args: ([], {}, {}))
    monkeypatch.setattr(resume.dev.base, "_require_paths", lambda output, menu: seen.append(menu))

    def complete(output, menu, rows, workers):
        seen.append(menu)
        rows[:] = [{"job": job} for job in menu]

    def summarize(rows, *args):
        assert [row["job"] for row in rows] == jobs
        return {"version": resume.dev.VERSION, "episodes": 32}

    monkeypatch.setattr(resume, "_complete_missing", complete)
    monkeypatch.setattr(resume.dev, "summarize", summarize)
    summary = resume.run(tmp_path, published_commit="fixture")
    assert seen == [jobs, jobs] and len(jobs) == 32
    assert (tmp_path / "summary.json").read_bytes() == resume.canonical(summary) + b"\n"


def test_verify_keeps_original_exact_replay_without_a_write_path(monkeypatch, tmp_path):
    (tmp_path / "summary.json").write_text("{}")
    monkeypatch.setattr(resume, "_assert_no_active_runner", lambda: None)
    monkeypatch.setattr(resume.dev.base, "_require_paths", lambda *args: None)
    monkeypatch.setattr(resume, "_load_saved", lambda *args: pytest.fail("resume path during replay"))

    def verify(output, **kwargs):
        assert kwargs["verify"] is True and kwargs["workers"] == 3
        return {"exact_episodes": 32}

    monkeypatch.setattr(resume.dev, "run", verify)
    assert resume.run(tmp_path, workers=3, verify=True) == {"exact_episodes": 32}
    assert (tmp_path / "summary.json").read_text() == "{}"


def test_advisory_lock_and_visible_original_runner_prevent_duplicates(monkeypatch, tmp_path):
    monkeypatch.setattr(resume.psutil, "process_iter", lambda: [])
    with resume._exclusive(tmp_path):
        with pytest.raises(ValueError, match="output lock"):
            with resume._exclusive(tmp_path):
                pytest.fail("duplicate runner admitted")
    process = SimpleNamespace(pid=-1, uids=lambda: SimpleNamespace(real=resume.os.getuid()),
                              cmdline=lambda: ["python", "/tmp/resume_commons_v3_joint_development_remaining.py"])
    monkeypatch.setattr(resume.psutil, "process_iter", lambda: [process])
    with pytest.raises(ValueError, match="runner still active"):
        with resume._exclusive(tmp_path):
            pytest.fail("old runner admitted")


def test_uninspectable_process_fails_closed(monkeypatch):
    def denied():
        raise resume.psutil.AccessDenied(pid=-1)

    process = SimpleNamespace(pid=-1, uids=lambda: SimpleNamespace(real=resume.os.getuid()), cmdline=denied)
    monkeypatch.setattr(resume.psutil, "process_iter", lambda: [process])
    with pytest.raises(ValueError, match="cannot inspect"):
        resume._assert_no_active_runner()
