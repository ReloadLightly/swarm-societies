"""Scientific invariants for v2 selection and matched fresh counterfactuals."""
from copy import deepcopy
import json
from pathlib import Path
import statistics
import tempfile
import unittest
from unittest.mock import patch

from scripts.evaluate_consumption_study import aggregate, case_metrics
from scripts.prepare_consumption_study import prepare_campaign
import swarm_societies.consumption_evaluation as selection
from swarm_societies.consumption_study import make_search_cases, simulate_consumption
from swarm_societies.evaluation import ROOT, read_json


def tiny_cases(wealth=20.):
    cases = deepcopy(make_search_cases(731)[:2])
    for case, ticks in zip(cases, (2, 4)):
        case["config"].update(ticks=ticks, disturbance_tick=ticks // 2,
                              initial_wealth=wealth, initial_patch=1., regeneration=.6)
    return cases


def write_program(path, action="harvest", institution="return {'tax_rate': 0, 'raid_permission': False}"):
    path.write_text("def member_policy(o, s):\n"
                    f" return {{'action': '{action}', 'target': o['society_id']}}\n"
                    "def institution(o, s):\n " + institution + "\n")
    return path


class ConsumptionSelectionTests(unittest.TestCase):
    def initialize(self, path, condition="coevolution", cases=None):
        return selection.initialize_context(path, condition, 1, 731,
                                            cases=tiny_cases() if cases is None else cases)

    def test_schedules_distinguish_search_islands_from_ecological_units(self):
        for condition in selection.CONDITIONS:
            state = {"condition": condition, "n_societies": 3, "members_per_society": 4}
            self.assertEqual(selection.target_for(state, 0), ("initial", 0, None))
            if condition == "coevolution":
                self.assertEqual([selection.target_for(state, i) for i in range(1, 9)], [
                    ("member", 0, 0), ("institution", 0, None),
                    ("member", 1, 0), ("institution", 1, None),
                    ("member", 2, 0), ("institution", 2, None),
                    ("member", 0, 1), ("institution", 0, None),
                ])
            else:
                self.assertTrue(all(selection.target_for(state, i)[0] == "member" for i in range(1, 25)))
                self.assertEqual(selection.target_for(state, 4), ("member", 0, 1))

    def test_fixed_institutions_never_change_and_member_selection_is_paired_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            base, context = Path(directory), Path(directory) / "context.json"
            initial = self.initialize(context, "fixed_institution")
            candidate = write_program(base / "greedy.py", institution="return {'tax_rate': .8, 'public_fraction': 1}")
            selection.evaluate_search(ROOT / "seeds/initial.py", base / "job0", context)
            with patch.object(selection, "simulate_consumption", wraps=simulate_consumption) as calls, \
                 patch("swarm_societies.consumption_study.make_fresh_cases", side_effect=AssertionError("fresh-case leak")):
                first = selection.evaluate_search(candidate, base / "job1", context)
            self.assertTrue(first["valid"])
            self.assertTrue(first["accepted"])
            after_first = read_json(context)
            self.assertEqual(after_first["institutions"], initial["institutions"])
            self.assertEqual(after_first["accepted_institution_updates"], 0)
            self.assertEqual(after_first["members"][0][0], first["program_path"])
            self.assertEqual(calls.call_count, 4)
            for i, case in enumerate(initial["search_cases"]):
                before_call, after_call = calls.call_args_list[2*i:2*i+2]
                self.assertEqual(before_call.args[2], after_call.args[2])
                self.assertEqual(before_call.args[2], case)
                self.assertEqual(before_call.args[0], after_call.args[0])
                before = simulate_consumption(initial["institutions"], initial["members"], case)
                after = simulate_consumption(after_first["institutions"], after_first["members"], case)
                self.assertEqual(first["case_objectives"]["incumbent"][i], before["member_metrics"][0]["utility"] / case["config"]["ticks"])
                self.assertEqual(first["case_objectives"]["candidate"][i], after["member_metrics"][0]["normalized_utility"])
            self.assertEqual(first["candidate_objective"], statistics.mean(first["case_objectives"]["candidate"]))
            feedback = read_json(base / "job1/metrics.json")["public"]
            self.assertEqual(feedback["condition"], "fixed_institution")
            self.assertNotIn("outcomes", feedback)
            self.assertIn("outcome_means", feedback)
            serialized_feedback = json.dumps(feedback)
            for case in initial["search_cases"]:
                for private in (case["id"], str(case["seed"]), str(case["schedule_seed"])):
                    self.assertNotIn(private, serialized_feedback)
            for private_key in ('"case"', '"config"', '"ticks"', '"disturbance_tick"', '"seed"'):
                self.assertNotIn(private_key, serialized_feedback)
            # Proposal content, including its different institution, cannot bypass
            # fixed-arm scheduling when the next society's member is replaced.
            second = selection.evaluate_search(candidate, base / "job2", context)
            self.assertEqual((second["kind"], second["target_society"]), ("member", 1))
            self.assertEqual(read_json(context)["institutions"], initial["institutions"])
            again = selection.evaluate_search(ROOT / "seeds/selfish.py", base / "job1", context)
            self.assertEqual(again, first)
            self.assertEqual(len(read_json(context)["evaluations"]), 3)
            self.assertNotIn("fresh", json.dumps(first))

    def test_institution_acceptance_uses_consumption_without_changing_members(self):
        with tempfile.TemporaryDirectory() as directory:
            base, context = Path(directory), Path(directory) / "context.json"
            cases = tiny_cases(wealth=0.)[:1]
            cases[0]["config"].update(ticks=4, disturbance_tick=2)
            initial = self.initialize(context, cases=cases)
            selection.evaluate_search(ROOT / "seeds/initial.py", base / "job0", context)
            rest = write_program(base / "rest.py", action="rest")
            member = selection.evaluate_search(rest, base / "job1", context)
            self.assertFalse(member["accepted"])
            institution = selection.evaluate_search(rest, base / "job2", context)
            self.assertTrue(institution["valid"])
            self.assertTrue(institution["accepted"])
            latest = read_json(context)
            self.assertEqual(latest["members"], initial["members"])
            self.assertEqual(latest["accepted_institution_updates"], 1)
            self.assertEqual(latest["institutions"][0], institution["program_path"])
            for i, case in enumerate(initial["search_cases"]):
                after = simulate_consumption(latest["institutions"], latest["members"], case)
                own = after["society_metrics"][0]["overall"]
                expected = (own["consumption"] - .5 * own["shortfall"]) / (4 * case["config"]["ticks"])
                self.assertEqual(institution["case_objectives"]["candidate"][i], expected)

    def test_invalid_candidate_cannot_change_population_or_receive_fitness_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            base, context = Path(directory), Path(directory) / "context.json"
            initial = self.initialize(context)
            selection.evaluate_search(ROOT / "seeds/initial.py", base / "job0", context)
            bad = base / "invalid.py"
            bad.write_text("import os\n")
            result = selection.evaluate_search(bad, base / "job1", context)
            self.assertFalse(result["valid"])
            self.assertFalse(result["accepted"])
            self.assertLess(result["combined_score"], 0)
            self.assertIn("unsupported syntax", result["error"])
            current = read_json(context)
            self.assertEqual(current["members"], initial["members"])
            self.assertEqual(current["institutions"], initial["institutions"])
            self.assertFalse(read_json(base / "job1/correct.json")["correct"])

    def test_snapshot_tampering_is_detected_before_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "context.json"
            state = self.initialize(context)
            Path(state["members"][0][0]).write_text("tampered\n")
            with self.assertRaises(ValueError):
                selection.verify_frozen_sources(state)

    def test_preparation_pairs_search_banks_and_freezes_disjoint_fresh_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = prepare_campaign(directory, replicates=2, minutes_per_run=3)
            self.assertEqual(len(plan["runs"]), 4)
            self.assertEqual(plan["total_search_minutes"], 12)
            self.assertFalse(plan["model_route"]["paid_api_allowed"])
            self.assertEqual(plan["fresh_cases_sha256"], selection.file_hash(plan["fresh_cases"]))
            self.assertEqual(plan["protocol_sha256"], selection.file_hash(plan["protocol"]))
            states = {(r["replicate"], r["condition"]): read_json(r["context"]) for r in plan["runs"]}
            for replicate in (1, 2):
                left = states[replicate, "coevolution"]
                right = states[replicate, "fixed_institution"]
                self.assertEqual(left["search_cases"], right["search_cases"])
                self.assertEqual([Path(p).stem for p in left["initial_institutions"]],
                                 [Path(p).stem for p in right["initial_institutions"]])
            self.assertNotEqual(states[1, "coevolution"]["search_cases"], states[2, "coevolution"]["search_cases"])
            search_seeds = {case["seed"] for state in states.values() for case in state["search_cases"]}
            fresh_seeds = {case["seed"] for case in read_json(plan["fresh_cases"])["cases"]}
            self.assertFalse(search_seeds & fresh_seeds)
            self.assertEqual(len({r["search_seed"] for r in plan["runs"]}), 4)
            self.assertTrue(all(0 <= r["search_seed"] < 2**32 for r in plan["runs"]))
            with self.assertRaises(ValueError):
                prepare_campaign(directory)

    def test_fresh_counterfactual_pairs_keep_sources_and_aggregate_normalized_cases(self):
        seeds = [str(ROOT / "seeds" / f"{name}.py") for name in ("initial", "cooperative", "selfish")]
        members = [[p] * 4 for p in seeds]
        rows = []
        for case in tiny_cases(wealth=0.):
            job = (case, "selfish", 0, seeds, members, seeds, members)
            with patch("scripts.evaluate_consumption_study.simulate_consumption", wraps=simulate_consumption) as calls:
                row = case_metrics(job)
            self.assertEqual(calls.call_count, 2)
            self.assertEqual(calls.call_args_list[0].args, calls.call_args_list[1].args)
            self.assertTrue(calls.call_args_list[0].kwargs["disturbance"])
            self.assertFalse(calls.call_args_list[1].kwargs["disturbance"])
            self.assertEqual(row["drought"]["pre_welfare"], row["no_drought"]["pre_welfare"])
            self.assertEqual(row["drought_welfare_effect"], row["drought"]["welfare"] - row["no_drought"]["welfare"])
            for name in ("drought", "no_drought"):
                ticks = case["config"]["ticks"]
                consumption = sum(m["consumption"] for m in row[name]["members"])
                shortfall = sum(m["shortfall"] for m in row[name]["members"])
                self.assertAlmostEqual(row[name]["welfare"], (consumption - .5 * shortfall) / (4 * ticks))
                self.assertAlmostEqual(row[name]["utility_per_tick"],
                                       statistics.mean(m["normalized_utility"] for m in row[name]["members"]))
            rows.append(row)
        summary = aggregate(rows)
        self.assertEqual((summary["n_cases"], summary["n_rollouts"]), (2, 4))
        self.assertEqual(summary["drought"]["welfare"], statistics.mean(r["drought"]["welfare"] for r in rows))
        self.assertEqual(summary["drought_welfare_effect"], statistics.mean(r["drought_welfare_effect"] for r in rows))


if __name__ == "__main__":
    unittest.main()
