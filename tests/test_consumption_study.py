from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
from pathlib import Path
import unittest

from swarm_societies.candidate import CandidateProgram
from swarm_societies.ecology import EcologyConfig as V1Config, run_episode as run_v1
from swarm_societies.ecology_consumption_v2 import EcologyConfig as V2Config, run_episode as run_v2
from swarm_societies.consumption_study import (
    FROZEN_V1_SIMULATOR_SHA256, SEARCH_SCHEDULES,
    make_fresh_cases, make_search_cases, simulate_consumption,
)


ROOT = Path(__file__).resolve().parents[1]
SEEDS = [ROOT / "seeds" / f"{name}.py" for name in ("initial", "cooperative", "selfish")]


def small_case():
    case = deepcopy(make_search_cases(731)[0])
    case["config"].update(ticks=17, disturbance_tick=6, initial_patch=8.)
    return case


class ConsumptionStudyTests(unittest.TestCase):
    def test_scenario_banks_are_reproducible_balanced_and_disjoint(self):
        search = make_search_cases(731)
        self.assertEqual(search, make_search_cases(731))
        self.assertEqual(sorted((s["config"]["ticks"], s["disturbance_fraction"]) for s in search),
                         sorted(SEARCH_SCHEDULES))
        self.assertNotEqual(search, make_search_cases(732))
        fresh = make_fresh_cases()
        self.assertEqual(fresh, make_fresh_cases())
        self.assertEqual(Counter(s["config"]["ticks"] for s in fresh), {48: 4, 60: 4, 72: 4})
        self.assertEqual(Counter(s["disturbance_fraction"] for s in fresh), {.35: 4, .5: 4, .65: 4})
        search_seeds = {s["seed"] for r in (731, 732, 733) for s in make_search_cases(r)}
        self.assertFalse(search_seeds & {s["seed"] for s in fresh})
        self.assertEqual(len(search_seeds), 18)
        for case in search + fresh:
            self.assertEqual(case["config"]["disturbance_tick"],
                             int(case["config"]["ticks"] * case["disturbance_fraction"]))
        # Mutating a returned scenario cannot change future bank construction.
        search[0]["config"]["ticks"] = 999
        self.assertNotEqual(search, make_search_cases(731))

    def test_v1_remains_frozen_and_v2_preserves_all_material_dynamics(self):
        self.assertEqual(hashlib.sha256((ROOT / "swarm_societies/ecology.py").read_bytes()).hexdigest(),
                         FROZEN_V1_SIMULATOR_SHA256)
        config = V1Config(n_societies=3, members_per_society=4, ticks=17, disturbance_tick=6)
        first = run_v1(SEEDS, config, seed=123, replay=True)
        second = run_v2(SEEDS, V2Config(**asdict(config)), seed=123, replay=True)
        for key in ("program_hashes", "member_program_hashes", "member_metrics", "ledger", "replay"):
            self.assertEqual(first[key], second[key], key)
        for old, new in zip(first["timeseries"], second["timeseries"]):
            self.assertEqual({k: v for k, v in old.items() if k != "welfare"},
                             {k: v for k, v in new.items() if k != "welfare"})
            self.assertAlmostEqual(old["welfare"] - new["welfare"], .03 * old["infrastructure"])
        self.assertGreater(first["ledger"]["investment"], 0)
        self.assertGreater(first["aggregate"]["mean_welfare"], second["aggregate"]["mean_welfare"])

    def test_consumption_measurement_uses_actual_phase_lengths_and_normalized_utilities(self):
        case = small_case()
        unchanged = deepcopy(case)
        result = simulate_consumption(SEEDS, None, case, replay=True)
        self.assertEqual(case, unchanged)
        self.assertEqual(result["study"]["phase_ticks"], {"pre": 6, "post": 11, "overall": 17})
        for society in result["society_metrics"]:
            for phase, ticks in result["study"]["phase_ticks"].items():
                metric = society[phase]
                self.assertAlmostEqual(metric["welfare"],
                                       (metric["consumption"] - .5 * metric["shortfall"]) / (4 * ticks))
                self.assertAlmostEqual(metric["welfare_with_infrastructure"] - metric["welfare"],
                                       .03 * metric["infrastructure"])
            self.assertAlmostEqual(society["normalized_mean_individual_utility"],
                                   society["mean_individual_utility"] / 17)
            self.assertAlmostEqual(society["adaptation"],
                                   society["post"]["welfare"] - society["pre"]["welfare"])
        for member in result["member_metrics"]:
            self.assertAlmostEqual(member["normalized_utility"], member["utility"] / 17)
        self.assertEqual(result["digest"], simulate_consumption(SEEDS, None, case, replay=True)["digest"])
        self.assertAlmostEqual(result["ledger"]["residual"], 0, places=8)

    def test_exact_no_drought_preserves_pairing_and_ignores_severity(self):
        case = small_case()
        case["config"]["drought_factor"] = 0.0
        treated = simulate_consumption(SEEDS, None, case, replay=True)
        control = simulate_consumption(SEEDS, None, case, replay=True, disturbance=False)
        self.assertEqual(treated["seed"], control["seed"])
        self.assertEqual(treated["program_hashes"], control["program_hashes"])
        self.assertEqual(treated["member_program_hashes"], control["member_program_hashes"])
        self.assertEqual(treated["replay"][:6], control["replay"][:6])
        self.assertEqual([s["pre"] for s in treated["society_metrics"]],
                         [s["pre"] for s in control["society_metrics"]])
        self.assertTrue(any(frame["disturbed"] for frame in treated["replay"]))
        self.assertFalse(any(frame["disturbed"] for frame in control["replay"]))
        self.assertGreater(control["ledger"]["regeneration"], treated["ledger"]["regeneration"])
        # A factor of 1 alone would retain random 0.85–1.15 severity. The switch
        # must ignore severity entirely, while consuming the same RNG draws.
        other = deepcopy(case)
        other["config"]["drought_factor"] = 99.0
        other_control = simulate_consumption(SEEDS, None, other, replay=True, disturbance=False)
        for key in ("ledger", "replay", "member_metrics", "society_metrics"):
            self.assertEqual(control[key], other_control[key], key)

    def test_schedules_and_scores_are_absent_from_candidate_observations(self):
        source = '''
def member_policy(observation, state):
    expected = ['tick', 'society_id', 'member_id', 'n_societies', 'n_members', 'wealth', 'productivity', 'infrastructure', 'tax_rate', 'patches', 'messages', 'last_action']
    if sorted(observation.keys()) != sorted(expected):
        return {'action': 'invalid'}
    return {'action': 'harvest', 'target': observation['society_id']}

def institution(observation, state):
    expected = ['tick', 'society_id', 'n_societies', 'treasury', 'infrastructure', 'mean_wealth', 'members', 'reports']
    if sorted(observation.keys()) != sorted(expected):
        return {'redistribution': []}
    return {'tax_rate': 0.2, 'public_fraction': 0.2}
'''
        program = CandidateProgram(source)
        result = simulate_consumption([program] * 3, None, small_case())
        self.assertTrue(all(member["actions"] == {"harvest": 17} for member in result["member_metrics"]))


if __name__ == "__main__":
    unittest.main()
