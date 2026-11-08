"""
evaluation/benchmark_hybrid.py - Benchmark HybridPolicy against the complete 12-opponent population.
"""

from __future__ import annotations

import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match
from runtime.hybrid_policy import HybridPolicy
from runtime.opponent import OpponentModel
from opponents.baselines import BASELINE_REGISTRY
from game import AgentConfig


def benchmark_hybrid(deals: int = 100, seed: str = "eval_hybrid"):
    print("=" * 80)
    print(f"BENCHMARK SUITE: HybridPolicy (CFR-10k + Adaptive Exploiter) vs 12 Opponents")
    print(f"Deals per match: {deals} duplicate (200 hands)")
    print("=" * 80)

    policy = HybridPolicy(cfr_checkpoint="assets/cfr_blueprint_10k.pkl", seed=42)

    def hybrid_new_half(config: AgentConfig, memory: dict):
        OpponentModel.init_memory(memory)

    def hybrid_end_hand(result, memory: dict):
        OpponentModel.update(result, memory)

    results = {}
    total_pts = 0.0

    for opp_name, opp_cls in BASELINE_REGISTRY.items():
        opp_inst = opp_cls()
        opp_fn = opp_inst.choose_action
        opp_end_fn = getattr(opp_inst, "on_hand_end", None)
        opp_new_half_fn = getattr(opp_inst, "new_half", None)

        match_res = play_local_match(
            agent1_fn=policy.choose_action,
            agent2_fn=opp_fn,
            agent1_end_fn=hybrid_end_hand,
            agent2_end_fn=opp_end_fn,
            agent1_new_half_fn=hybrid_new_half,
            agent2_new_half_fn=opp_new_half_fn,
            seed=f"{seed}_{opp_name}",
            num_deals=deals,
        )
        results[opp_name] = match_res
        ci_str = f"[{match_res.ci[0]:+.2f}, {match_res.ci[1]:+.2f}]"
        pts = 1.0 if match_res.verdict == "AGENT1_WIN" else (0.5 if match_res.verdict == "CHOP" else 0.0)
        total_pts += pts
        print(f"vs {opp_name:<24} | {match_res.verdict:<12} | {match_res.mean_bb:+8.2f} bb/deal | {ci_str:<18} | Pts: {pts}")

    print("=" * 80)
    print(f"TOTAL MATCH POINTS: {total_pts:.1f} / {len(BASELINE_REGISTRY)} ({total_pts/len(BASELINE_REGISTRY)*100:.1f}%)")
    return results


if __name__ == "__main__":
    deals = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    benchmark_hybrid(deals)
