"""
evaluation/compare_draw_aware.py - Head-to-head comparison between RangeAware_v2
and DrawAware_v1 across critical and adversarial opponents.

Runs identical matched-seed duplicate matches with fresh policy instances per half.
"""

from __future__ import annotations

import sys
import os
import time
import json
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import warmup
warmup()

from evaluation.local_match import play_local_match_fresh, LocalMatchResult, format_local_result
from runtime.range_aware_policy import RangeAwarePolicy
from runtime.draw_aware_policy import DrawAwarePolicy
from opponents.baselines import BASELINE_REGISTRY
from opponents.adversarial import ADVERSARIAL_REGISTRY

ALL_OPPONENTS = {**BASELINE_REGISTRY, **ADVERSARIAL_REGISTRY}


def run_candidate_vs_opp(candidate_cls, opp_cls, opp_name: str, seed: str, deals: int = 500) -> LocalMatchResult:
    def make_cand():
        pol = candidate_cls(aggression=1.0, seed=42, num_samples=30)
        return pol.choose_action, None, None

    def make_opp():
        bot = opp_cls()
        end_fn = getattr(bot, "on_hand_end", None)
        new_half_fn = getattr(bot, "new_half", None)
        return bot.choose_action, end_fn, new_half_fn

    return play_local_match_fresh(make_cand, make_opp, seed=seed, num_deals=deals)


def main():
    test_opponents = [
        "calling_station",
        "action_conditioned_range",
        "size_aware_equity",
        "street_inversion_attacker",
        "draw_aware_opponent",
    ]
    seeds = ["cmp_draw_seed_1", "cmp_draw_seed_2"]
    deals = 500

    results = []

    print("=" * 80)
    print(f"HEAD-TO-HEAD CANDIDATE COMPARISON ({deals} duplicate deals per match, fresh halves)")
    print("=" * 80)

    for opp_name in test_opponents:
        opp_cls = ALL_OPPONENTS.get(opp_name)
        if not opp_cls:
            print(f"Skipping unknown opponent: {opp_name}")
            continue

        for seed in seeds:
            print(f"\n--- Opponent: {opp_name} | Seed: {seed} ---")

            # 1. RangeAware_v2
            t0 = time.perf_counter()
            res_ra = run_candidate_vs_opp(RangeAwarePolicy, opp_cls, opp_name, seed, deals)
            ra_time = time.perf_counter() - t0

            # 2. DrawAware_v1
            t0 = time.perf_counter()
            res_da = run_candidate_vs_opp(DrawAwarePolicy, opp_cls, opp_name, seed, deals)
            da_time = time.perf_counter() - t0

            delta = res_da.mean_bb - res_ra.mean_bb

            print(f"  RangeAware_v2: {res_ra.mean_bb:+.3f} BB/deal, 95% CI [{res_ra.ci[0]:+.3f}, {res_ra.ci[1]:+.3f}] -> {res_ra.verdict} ({ra_time:.2f}s)")
            print(f"  DrawAware_v1:  {res_da.mean_bb:+.3f} BB/deal, 95% CI [{res_da.ci[0]:+.3f}, {res_da.ci[1]:+.3f}] -> {res_da.verdict} ({da_time:.2f}s)")
            print(f"  Delta (DA - RA): {delta:+.3f} BB/deal")

            results.append({
                "opponent": opp_name,
                "seed": seed,
                "deals": deals,
                "ra_mean_bb": res_ra.mean_bb,
                "ra_ci": list(res_ra.ci),
                "ra_verdict": res_ra.verdict,
                "ra_time_s": ra_time,
                "da_mean_bb": res_da.mean_bb,
                "da_ci": list(res_da.ci),
                "da_verdict": res_da.verdict,
                "da_time_s": da_time,
                "delta_bb": delta,
            })

    out_path = os.path.join(ROOT_DIR, "reports", "raw_matches", "draw_aware_comparison.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved raw results to {out_path}")


if __name__ == "__main__":
    main()
