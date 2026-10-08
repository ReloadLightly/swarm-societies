"""A1 gate and runner fixtures; no declared development arena executes here."""
from copy import deepcopy
import math

import pytest

from swarm_societies.commons_v3 import development_learning_sites_v1 as base
from swarm_societies.commons_v3 import development_pool_sites_v1 as development
from swarm_societies.commons_v3 import engine_sites_v1 as engine
from swarm_societies.commons_v3.development_navigation_v1 import _save_record


def row(job, *, share=.8, early=.7):
    return {
        "job": deepcopy(job), "horizon": 512,
        "summary": {
            "share_of_need": share,
            "first64_share_of_need": early,
            "final_quarter_share_of_need": .8,
            "terminal_capacity_absolute_log_error": .2,
            "time_mean_capacity_absolute_log_error": .3,
            "terminal_seen_only_absolute_log_error": .1,
            "time_mean_seen_only_absolute_log_error": .15,
        },
    }


def cases(*, pooled=.82, asocial=.8):
    return ([row(job, share=pooled) for job in development.pool_jobs()],
            [row(job, share=asocial) for job in base.candidate_jobs(.25)])


def test_pool_menu_reuses_the_sixteen_selected_development_worlds():
    jobs = development.pool_jobs()
    expected = [{**job, "arm": "R-pool"} for job in base.candidate_jobs(.25)]
    assert jobs == expected
    assert len(jobs) == 16
    assert {job["seed"] for job in jobs} == {90001, 90002, 90003, 90004}
    assert {job["q"] for job in jobs} == {.25}
    assert {job["phi"] for job in jobs} == {.375}
    assert len({base.case_id(job) for job in jobs}) == 16


@pytest.mark.parametrize("pooled,expected", [(.02, True), (math.nextafter(.02, 0.), False)])
def test_g3_prime_uses_inclusive_mean_threshold_without_an_interval_gate(pooled, expected):
    pool_rows, l0_rows = cases(pooled=pooled, asocial=0.)
    result = development.g3_prime(pool_rows, l0_rows)
    assert result["passed"] is expected
    assert result["threshold"] == .02
    assert result["condition"] == "wide" and result["need"] == 1.6
    assert len(result["cells"]) == 4
    selected = next(cell for cell in result["cells"] if cell["condition"] == "wide" and cell["need"] == 1.6)
    assert selected["pool_minus_L0"]["mean"] == pooled
    assert [pair["seed"] for pair in selected["paired"]] == [90001, 90002, 90003, 90004]
    assert all(pair["R-pool"] == pooled and pair["L0"] == 0.
               and pair["pool_minus_L0"] == pooled for pair in selected["paired"])


def test_g3_prime_requires_only_wide_high_whole_run_contrast():
    pool_rows, l0_rows = cases(pooled=.1, asocial=.8)
    for record in pool_rows:
        if record["job"]["condition"] == "wide" and record["job"]["need"] == 1.6:
            record["summary"]["share_of_need"] = .83
        record["summary"]["first64_share_of_need"] = 0.
    for record in l0_rows:
        record["summary"]["first64_share_of_need"] = 1.
    result = development.g3_prime(pool_rows, l0_rows)
    assert result["passed"]
    assert sum(cell["pool_minus_L0"]["mean"] >= .02 for cell in result["cells"]) == 1
    # Reverse the early result: whole-run consumption still controls the gate.
    for record in pool_rows:
        record["summary"]["share_of_need"] = .81
        record["summary"]["first64_share_of_need"] = 1.
    for record in l0_rows:
        record["summary"]["first64_share_of_need"] = 0.
    assert not development.g3_prime(pool_rows, l0_rows)["passed"]


def test_g3_prime_pairs_by_seed_and_uses_mean_not_every_seed_or_ci():
    pool_rows, l0_rows = cases(pooled=.8, asocial=.8)
    deltas = dict(zip((90001, 90002, 90003, 90004), (-.1, -.1, .2, .2)))
    for record in pool_rows:
        if record["job"]["condition"] == "wide" and record["job"]["need"] == 1.6:
            record["summary"]["share_of_need"] += deltas[record["job"]["seed"]]
    result = development.g3_prime(list(reversed(pool_rows)), l0_rows[5:] + l0_rows[:5])
    selected = next(cell for cell in result["cells"] if cell["condition"] == "wide" and cell["need"] == 1.6)
    assert result["passed"]
    assert selected["pool_minus_L0"]["mean"] == pytest.approx(.05)
    assert selected["pool_minus_L0"]["ci95"][0] < 0.
    assert [pair["pool_minus_L0"] for pair in selected["paired"]] == pytest.approx(list(deltas.values()))


@pytest.mark.parametrize("arm", ["pool", "L0"])
@pytest.mark.parametrize("damage", ["missing", "duplicate", "q", "phi", "seed", "arm", "horizon", "nan", "infinity"])
def test_g3_prime_rejects_incomplete_changed_or_nonfinite_records(arm, damage):
    pool_rows, l0_rows = cases()
    target = pool_rows if arm == "pool" else l0_rows
    if damage == "missing":
        target.pop()
    elif damage == "duplicate":
        target[-1] = deepcopy(target[0])
    elif damage in ("q", "phi", "seed", "arm"):
        target[0]["job"][damage] = {"q": .5, "phi": .5, "seed": 90005, "arm": "R-oracle"}[damage]
    elif damage == "horizon":
        target[0]["horizon"] = 64
    else:
        target[0]["summary"]["share_of_need"] = math.nan if damage == "nan" else math.inf
    with pytest.raises(ValueError):
        development.g3_prime(pool_rows, l0_rows)


def test_short_pool_fixture_replays_with_zero_traffic_and_terminal_assimilation():
    from swarm_societies.commons_v3.policies_pool_sites_v1 import PoolCoordinator, PoolForager
    cfg = engine.Config(width=6, height=3, n_agents=2, n_patches=2,
                        need=1.2, max_messages=1, sensing_radius=0,
                        site_capacities=(20., 60.), initial_site_stocks=(12., 36.))
    state = engine.WorldState(
        cfg, 42, 0,
        (engine.AgentState(0, 1, 1, 3.), engine.AgentState(1, 4, 1, 3.)),
        (engine.PatchState(0, 1, 1, 12.), engine.PatchState(1, 4, 1, 36.)),
    )
    job = {"arm": "R-pool", "need": 1.2, "phi": .375, "q": .25,
           "seed": 42, "condition": "unit fixture"}

    def execute():
        coordinator = PoolCoordinator()
        policies = [PoolForager(coordinator, i) for i in range(2)]
        record = development._record_pool_episode(job, state, policies, coordinator, horizon=8)
        return record, coordinator, policies

    recorded, coordinator, policies = execute()
    assert recorded == execute()[0]
    assert recorded["horizon"] == 8 and len(recorded["ticks"]) == 8
    assert [frame["tick"] for frame in recorded["belief_ticks"]] == list(range(9))
    assert recorded["belief_checkpoints"][-1]["tick"] == 8
    assert len(recorded["belief_checkpoints"][-1]["pairs"]) == 4
    assert recorded["summary"]["max_ledger_residual"] < 1e-10
    for key in ("message_attempts", "messages_delivered", "message_attempted_bytes",
                "message_paid_bytes", "message_delivered_bytes", "message_cost"):
        assert recorded["summary"][key] == 0
    assert coordinator.tick == 8
    assert any(update["kind"] == "growth" and update["tick"] == 7 for update in coordinator.last_updates)
    assert all(policy._observed_tick == 8 and policy._acted_tick == 7 for policy in policies)
    assert all(not policy.last_action.messages for policy in policies)


def rich_row(job, *, share=.8, error=.3, seen_error=.2, messages=4):
    record = row(job, share=share)
    record["initial_snapshot"] = {"state": {
        "seed": job["seed"], "condition": job["condition"],
        "config": {"max_messages": messages, "need": job["need"]},
        "agents": [{"id": i} for i in range(24)],
    }}
    record["weather_sha256"] = f"weather-{job['seed']}"
    record["summary"].update({
        "time_mean_capacity_absolute_log_error": error,
        "terminal_capacity_absolute_log_error": error / 2,
        "terminal_seen_only_absolute_log_error": seen_error / 2,
        "time_mean_seen_only_absolute_log_error": 777.,  # Derived from ticks instead.
        "time_mean_coverage90": .9, "terminal_coverage90": .9,
    })
    record["belief_ticks"] = [{"tick": t,
        "capacity_absolute_log_error": error,
        "seen_only_absolute_log_error": seen_error,
        "coverage90": .9,
    } for t in range(513)]
    return record


def summary_fixtures():
    pool_rows = [rich_row(job, share=.85, error=.2, seen_error=.1)
                 for job in development.pool_jobs()]
    l0_rows = [rich_row(job, share=.8, error=.6, seen_error=.3)
               for job in base.candidate_jobs(.25)]
    references = []
    for job in base.candidate_jobs(.25):
        for arm in ("R-oracle", "R-fixed", "R-greedy"):
            reference = {key: value for key, value in job.items() if key != "q"}
            reference.update(arm=arm, fixed_capacity=40. if arm == "R-fixed" else None)
            references.append(rich_row(reference, messages=1))
    return pool_rows, l0_rows, references


def test_pool_summary_reports_paired_all_and_seen_errors_without_changing_saved_l0():
    pool_rows, l0_rows, references = summary_fixtures()
    originals = deepcopy((l0_rows, references))
    summary = development.summarize_pool(pool_rows, l0_rows, references, {"preserved_G3": {"trivial": True}})
    assert summary["episodes"] == summary["L0_episodes_reused"] == 16
    assert summary["reference_episodes_reused"] == 48
    assert summary["phi"] == .375 and summary["q"] == .25 and summary["rate_known"]
    assert summary["G3_prime"]["passed"]
    assert summary["baseline"]["preserved_G3"]["trivial"]
    assert summary["fresh_evaluation_episodes"] == summary["experimental_model_calls"] == 0
    assert "descriptive" in summary["scope"]
    for cell in summary["cells"]:
        stats = cell["contrasts"]["R-pool_minus_L0"]["statistics"]
        expected = {"share_of_need": .05,
                    "time_mean_capacity_absolute_log_error": -.4,
                    "terminal_capacity_absolute_log_error": -.2,
                    "time_mean_seen_only_absolute_log_error": -.2,
                    "terminal_seen_only_absolute_log_error": -.1}
        for key, difference in expected.items():
            assert stats[key]["mean"] == pytest.approx(difference)
            assert stats[key]["n"] == 4
        assert len(cell["belief_trajectories"]["R-pool"]) == len(base.BELIEF_CHECKPOINTS)
    assert (l0_rows, references) == originals


@pytest.mark.parametrize("damage", ["weather", "initial_world"])
def test_pool_summary_rejects_unpaired_worlds_or_weather(damage):
    pool_rows, l0_rows, references = summary_fixtures()
    if damage == "weather":
        pool_rows[0]["weather_sha256"] = "different"
    else:
        pool_rows[0]["initial_snapshot"]["state"]["agents"][0]["inventory"] = 1.
    with pytest.raises(ValueError, match="initialization or weather"):
        development.summarize_pool(pool_rows, l0_rows, references, {})


class ImmediatePool:
    def __init__(self, **_):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def map(self, function, jobs):
        return map(function, jobs)


def test_pool_recovery_replays_and_preserves_existing_compressed_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(development, "ProcessPoolExecutor", ImmediatePool)
    jobs = development.pool_jobs()[:2]
    path = base._path(tmp_path, jobs[0])
    _save_record(path, row(jobs[0]))
    original = path.read_bytes()
    assert len(development._run_jobs(tmp_path, jobs, 1, row)) == 2
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="exact replay differs"):
        development._run_jobs(tmp_path, jobs, 1, lambda job: row(job, share=.1))
    assert path.read_bytes() == original


def test_pool_verification_does_not_write_a_missing_case(monkeypatch, tmp_path):
    monkeypatch.setattr(development, "ProcessPoolExecutor", ImmediatePool)
    job = development.pool_jobs()[0]
    with pytest.raises(ValueError, match="missing case during verification"):
        development._run_jobs(tmp_path, [job], 1, row, verify=True)
    assert not base._path(tmp_path, job).exists()


@pytest.mark.parametrize("passed", [False, True])
def test_sharing_submission_requires_passing_g3_prime_and_uses_only_declared_jobs(monkeypatch, tmp_path, passed):
    submitted = []
    monkeypatch.setattr(development, "load_baseline", lambda *_: ([], [], {}))
    monkeypatch.setattr(development, "_load_pool", lambda *_: ([], {"G3_prime": {"passed": passed}}))
    monkeypatch.setattr(base, "_require_paths", lambda *_: None)
    monkeypatch.setattr(development, "summarize_sharing", lambda rows, *_: {"episodes": len(rows)})

    def fake_run(output, jobs, workers, runner, *, verify=False):
        assert runner is base.run_episode and not verify
        submitted.extend(jobs)
        return [row(job) for job in jobs]

    monkeypatch.setattr(development, "_run_jobs", fake_run)
    if passed:
        result = development.run_sharing(tmp_path, workers=1)
        assert result["episodes"] == 80
        assert submitted == base.candidate_jobs(.25, base.ARMS[1:])
        with pytest.raises(ValueError, match="completed sharing"):
            development.run_sharing(tmp_path, workers=1)
        assert len(submitted) == 80
    else:
        with pytest.raises(ValueError, match="G3-prime failed"):
            development.run_sharing(tmp_path, workers=1)
        assert submitted == []
