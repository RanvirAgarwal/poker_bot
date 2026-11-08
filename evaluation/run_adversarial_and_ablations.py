"""
evaluation/run_adversarial_and_ablations.py - Evaluates RangeAware_v2 against the targeted
adversarial suite, runs ablation studies, and logs decision statistics.
"""

from __future__ import annotations

import sys
import os
import json
import time
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match
from evaluation.summary_table import summarize_results, format_markdown_table
from runtime.range_aware_policy import RangeAwarePolicy
from runtime.policy import HeuristicPolicy
from runtime.ablations import AblationPolicy
from opponents.adversarial import ADVERSARIAL_REGISTRY

RAW_DIR = os.path.join(ROOT_DIR, "reports", "raw_matches")
os.makedirs(RAW_DIR, exist_ok=True)


def run_adversarial_suite(deals: int = 100, seed: str = "adv_eval"):
    print("=" * 80)
    print(f"TARGETED ADVERSARIAL EVALUATION ({deals} deals, seed: {seed})")
    print("Testing RangeAware_v2 and EquityBot_v1 against 9 targeted stress-test opponents")
    print("=" * 80)

    p_range = RangeAwarePolicy(aggression=1.0, seed=42)
    p_equity = HeuristicPolicy(aggression=1.0, seed=42)

    range_results = {}
    equity_results = {}

    for name, cls in ADVERSARIAL_REGISTRY.items():
        opp = cls(seed=999)
        seed_str = f"{seed}_{name}"

        # 1. RangeAware_v2
        t0 = time.time()
        res_r = play_local_match(p_range.choose_action, opp.choose_action, seed=seed_str, num_deals=deals)
        res_r.elapsed_seconds = time.time() - t0
        range_results[name] = res_r

        # 2. EquityBot_v1 (matched seed)
        opp = cls(seed=999)
        t0 = time.time()
        res_e = play_local_match(p_equity.choose_action, opp.choose_action, seed=seed_str, num_deals=deals)
        res_e.elapsed_seconds = time.time() - t0
        equity_results[name] = res_e

        # Save raw JSONs
        with open(os.path.join(RAW_DIR, f"RangeAware_vs_{name}_{deals}deals.json"), "w") as f:
            json.dump({
                "candidate": "RangeAware_v2",
                "opponent": name,
                "deals": deals,
                "seed": seed_str,
                "mean_bb": res_r.mean_bb,
                "ci": list(res_r.ci),
                "verdict": res_r.verdict,
            }, f, indent=2)

        ci_r = f"[{res_r.ci[0]:+.2f}, {res_r.ci[1]:+.2f}]"
        ci_e = f"[{res_e.ci[0]:+.2f}, {res_e.ci[1]:+.2f}]"
        print(f"vs {name:<26} | RangeAware: {res_r.mean_bb:+6.2f} bb ({res_r.verdict:<10}) {ci_r} | EquityBot: {res_e.mean_bb:+6.2f} bb ({res_e.verdict:<10}) {ci_e}")

    sum_r = summarize_results(range_results)
    sum_e = summarize_results(equity_results)

    print("\n" + format_markdown_table("RangeAware_v2 vs Adversarial Suite", sum_r))
    print("\n" + format_markdown_table("EquityBot_v1 vs Adversarial Suite", sum_e))

    return range_results, equity_results


def run_ablations(deals: int = 100, seed: str = "ablation_eval"):
    print("\n" + "=" * 80)
    print("ABLATION STUDY: Isolating Range Conditioning, Adaptation, and Continuation")
    print(f"Deals per match: {deals}")
    print("=" * 80)

    test_opponents = {
        "calling_station": None,
        "always_raise": None,
        "action_conditioned_range": None,
        "street_inversion_attacker": None,
        "check_trap_attacker": None,
    }

    # Initialize opponents
    from opponents.baselines import CallingStationBot, AlwaysRaiseBot, ActionConditionedRangeBot
    from opponents.adversarial import StreetInversionAttacker, CheckTrapAttacker
    test_opponents["calling_station"] = CallingStationBot
    test_opponents["always_raise"] = AlwaysRaiseBot
    test_opponents["action_conditioned_range"] = ActionConditionedRangeBot
    test_opponents["street_inversion_attacker"] = StreetInversionAttacker
    test_opponents["check_trap_attacker"] = CheckTrapAttacker

    variants = {
        "1_EquityOnly": AblationPolicy(enable_range_conditioning=False, enable_aggression_adaptation=False, enable_continuation_filter=False, seed=42),
        "2_RangeOnly": AblationPolicy(enable_range_conditioning=True, enable_aggression_adaptation=False, enable_continuation_filter=False, seed=42),
        "3_RangeAndAdapt": AblationPolicy(enable_range_conditioning=True, enable_aggression_adaptation=True, enable_continuation_filter=False, seed=42),
        "4_Complete_v2": AblationPolicy(enable_range_conditioning=True, enable_aggression_adaptation=True, enable_continuation_filter=True, seed=42),
    }

    ablation_matrix = {}

    for var_name, policy in variants.items():
        ablation_matrix[var_name] = {}
        for opp_name, opp_cls in test_opponents.items():
            opp = opp_cls()
            seed_str = f"{seed}_{opp_name}"
            res = play_local_match(policy.choose_action, opp.choose_action, seed=seed_str, num_deals=deals)
            ablation_matrix[var_name][opp_name] = res.mean_bb

    print("\n### Ablation Matrix: Mean BB / deal")
    header = f"| Variant | {' | '.join(test_opponents.keys())} | Average |"
    sep = f"|:---|{'---:|' * len(test_opponents)}---:|"
    print(header)
    print(sep)

    for var_name, scores in ablation_matrix.items():
        row_vals = [f"{scores[opp]:+6.2f}" for opp in test_opponents.keys()]
        avg_val = sum(scores.values()) / len(scores)
        print(f"| `{var_name}` | {' | '.join(row_vals)} | **{avg_val:+6.2f}** |")

    with open(os.path.join(RAW_DIR, "ablation_results.json"), "w") as f:
        json.dump(ablation_matrix, f, indent=2)

    return ablation_matrix


if __name__ == "__main__":
    run_adversarial_suite(deals=100)
    run_ablations(deals=100)

