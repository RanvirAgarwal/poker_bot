"""
evaluation/compare_candidates.py - Head-to-head comparison between candidates across opponent suites.
"""

from __future__ import annotations

import sys
import os
import argparse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match, format_local_result
from runtime.policy import HeuristicPolicy
from runtime.cfr_policy import CFRPolicy
from opponents.baselines import BASELINE_REGISTRY


def run_candidate_comparison(ckpt_path: str, deals: int = 100, seed: str = "eval_compare"):
    print("=" * 75)
    print(f"CANDIDATE COMPARISON: EquityBot_v1 vs CFRBot ({ckpt_path})")
    print(f"Deals per match: {deals} duplicate (200 hands)")
    print("=" * 75)

    p_equity = HeuristicPolicy(aggression=1.0, seed=42)
    p_cfr = CFRPolicy(checkpoint_path=ckpt_path, seed=42)

    # 1. Direct Head-to-Head: EquityBot vs CFRBot
    print("\n[MATCH 1] Direct Head-to-Head: EquityBot_v1 vs CFRBot")
    h2h_result = play_local_match(
        agent1_fn=p_equity.choose_action,
        agent2_fn=p_cfr.choose_action,
        seed=f"{seed}_h2h",
        num_deals=deals,
    )
    print(format_local_result(h2h_result, name1="EquityBot_v1", name2="CFRBot"))

    # 2. CFRBot vs Key Opponents
    print("\n" + "=" * 75)
    print(f"CFRBot ({ckpt_path}) vs Complete Opponent Suite")
    print("=" * 75)

    cfr_results = {}
    for opp_name, opp_cls in BASELINE_REGISTRY.items():
        opp_inst = opp_cls()
        match_res = play_local_match(
            agent1_fn=p_cfr.choose_action,
            agent2_fn=opp_inst.choose_action,
            seed=f"{seed}_{opp_name}",
            num_deals=deals,
        )
        cfr_results[opp_name] = match_res
        ci_str = f"[{match_res.ci[0]:+.2f}, {match_res.ci[1]:+.2f}]"
        print(f"vs {opp_name:<24} | {match_res.verdict:<12} | {match_res.mean_bb:+8.2f} bb/deal | {ci_str:<18}")

    return h2h_result, cfr_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="assets/cfr_blueprint_10k.pkl")
    parser.add_argument("--deals", type=int, default=100)
    args = parser.parse_args()

    run_candidate_comparison(args.checkpoint, deals=args.deals)

