"""
evaluation/run_critical_multiseed_evaluation.py - 5-Seed 1,000-deal duplicate evaluations of RangeAware_v2 vs EquityBot_v1 across critical opponents.

Critical opponents:
- action_conditioned_range
- size_aware_equity
- always_raise
- adaptive_exploiter
- frozen_equity_attacker
- calling_station (regression check)
"""

from __future__ import annotations

import sys
import os
import json
import time
from typing import Dict, List, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match
from runtime.policy import HeuristicPolicy
from runtime.range_aware_policy import RangeAwarePolicy
from opponents.baselines import BASELINE_REGISTRY

CRITICAL_OPPONENTS = [
    "action_conditioned_range",
    "size_aware_equity",
    "always_raise",
    "adaptive_exploiter",
    "frozen_equity_attacker",
    "calling_station",
]

SEEDS = [101, 202, 303, 404, 505]
NUM_DEALS = 1000
RAW_DIR = os.path.join(ROOT_DIR, "reports", "raw_matches")
os.makedirs(RAW_DIR, exist_ok=True)


def run_multiseed_eval():
    print("=" * 80)
    print(f"CRITICAL MULTI-SEED EVALUATION (5 seeds x {NUM_DEALS} deals = 10,000 hands per opponent)")
    print("Candidates: EquityBot_v1 vs RangeAware_v2")
    print(f"Opponents: {', '.join(CRITICAL_OPPONENTS)}")
    print("=" * 80)

    p_equity = HeuristicPolicy(aggression=1.0, seed=42)
    p_range = RangeAwarePolicy(aggression=1.0, seed=42)

    all_data = {
        "seeds": SEEDS,
        "deals_per_seed": NUM_DEALS,
        "opponents": {},
    }

    for opp_name in CRITICAL_OPPONENTS:
        opp_cls = BASELINE_REGISTRY[opp_name]
        print(f"\n>>> EVALUATING VS {opp_name.upper()} <<<")
        all_data["opponents"][opp_name] = {
            "RangeAware_v2": [],
            "EquityBot_v1": [],
        }

        for s in SEEDS:
            seed_str = f"seed_{s}_{opp_name}"
            # 1. RangeAware_v2
            opp_inst = opp_cls()
            t0 = time.time()
            res_range = play_local_match(
                agent1_fn=p_range.choose_action,
                agent2_fn=opp_inst.choose_action,
                seed=seed_str,
                num_deals=NUM_DEALS,
            )
            t_range = time.time() - t0

            # 2. EquityBot_v1 (matched seed)
            opp_inst = opp_cls()
            t0 = time.time()
            res_equity = play_local_match(
                agent1_fn=p_equity.choose_action,
                agent2_fn=opp_inst.choose_action,
                seed=seed_str,
                num_deals=NUM_DEALS,
            )
            t_equity = time.time() - t0

            all_data["opponents"][opp_name]["RangeAware_v2"].append({
                "seed": s,
                "mean_bb": res_range.mean_bb,
                "ci": list(res_range.ci),
                "verdict": res_range.verdict,
                "time": t_range,
            })
            all_data["opponents"][opp_name]["EquityBot_v1"].append({
                "seed": s,
                "mean_bb": res_equity.mean_bb,
                "ci": list(res_equity.ci),
                "verdict": res_equity.verdict,
                "time": t_equity,
            })

            print(f"  Seed {s:<4} | RangeAware: {res_range.mean_bb:+6.2f} bb ({res_range.verdict:<10}) | EquityBot: {res_equity.mean_bb:+6.2f} bb ({res_equity.verdict:<10})")

    out_file = os.path.join(RAW_DIR, "critical_multiseed_comparison.json")
    with open(out_file, "w") as f:
        json.dump(all_data, f, indent=2)

    print("\n" + "=" * 80)
    print("MULTI-SEED AGGREGATE SUMMARY (Across 5 Seeds)")
    print("=" * 80)
    print("| Opponent | EquityBot Mean BB | RangeAware Mean BB | Delta (BB) | EquityBot Record | RangeAware Record |")
    print("|:---|:---:|:---:|:---:|:---:|:---:|")

    for opp_name in CRITICAL_OPPONENTS:
        r_list = all_data["opponents"][opp_name]["RangeAware_v2"]
        e_list = all_data["opponents"][opp_name]["EquityBot_v1"]

        r_mean = sum(x["mean_bb"] for x in r_list) / len(r_list)
        e_mean = sum(x["mean_bb"] for x in e_list) / len(e_list)
        delta = r_mean - e_mean

        r_w = sum(1 for x in r_list if x["verdict"] == "AGENT1_WIN")
        r_c = sum(1 for x in r_list if x["verdict"] == "CHOP")
        r_l = sum(1 for x in r_list if x["verdict"] == "AGENT2_WIN")

        e_w = sum(1 for x in e_list if x["verdict"] == "AGENT1_WIN")
        e_c = sum(1 for x in e_list if x["verdict"] == "CHOP")
        e_l = sum(1 for x in e_list if x["verdict"] == "AGENT2_WIN")

        print(f"| `{opp_name}` | {e_mean:+6.2f} bb | {r_mean:+6.2f} bb | {delta:+6.2f} bb | {e_w}W-{e_c}C-{e_l}L | {r_w}W-{r_c}C-{r_l}L |")

    return all_data


if __name__ == "__main__":
    run_multiseed_eval()

