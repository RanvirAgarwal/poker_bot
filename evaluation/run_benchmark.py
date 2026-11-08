"""
evaluation/run_benchmark.py - Benchmark our agent against opponent baselines.

Runs duplicate matches (both halves, paired BB, 95% CI) against each baseline opponent.
Outputs a clean summary table of results.
"""

from __future__ import annotations

import sys
import os
import importlib.util

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match, format_local_result
from opponents.baselines import BASELINE_REGISTRY

# Explicitly load root agent.py to avoid collisions with starter/agent.py
spec = importlib.util.spec_from_file_location("root_agent", os.path.join(ROOT_DIR, "agent.py"))
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def run_benchmark(num_deals: int = 200, seed: str = "bench_seed_1"):
    print("=" * 70)
    print(f"BENCHMARK SUITE: {agent.AGENT_NAME} vs Baselines ({num_deals} deals)")
    print("=" * 70)

    results = {}
    agent_fn = agent.choose_action
    agent_end_fn = agent.on_hand_end
    agent_new_half_fn = agent.new_half

    for opp_name, opp_cls in BASELINE_REGISTRY.items():
        opp_instance = opp_cls()
        opp_fn = opp_instance.choose_action
        opp_end_fn = getattr(opp_instance, "on_hand_end", None)
        opp_new_half_fn = getattr(opp_instance, "new_half", None)

        print(f"\n--- Playing vs {opp_name} ({opp_cls.__name__}) ---")
        match_result = play_local_match(
            agent1_fn=agent_fn,
            agent2_fn=opp_fn,
            agent1_end_fn=agent_end_fn,
            agent2_end_fn=opp_end_fn,
            agent1_new_half_fn=agent_new_half_fn,
            agent2_new_half_fn=opp_new_half_fn,
            seed=f"{seed}_{opp_name}",
            num_deals=num_deals,
        )
        results[opp_name] = match_result
        print(format_local_result(match_result, name1=agent.AGENT_NAME, name2=opp_name))

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print(f"{'Opponent':<18} | {'Verdict':<12} | {'Mean BB/deal':<14} | {'95% CI':<20} | {'Time (s)':<8}")
    print("-" * 78)
    for opp_name, res in results.items():
        ci_str = f"[{res.ci[0]:+.2f}, {res.ci[1]:+.2f}]"
        print(f"{opp_name:<18} | {res.verdict:<12} | {res.mean_bb:+10.3f}   | {ci_str:<20} | {res.elapsed_seconds:<8.2f}")

    return results


if __name__ == "__main__":
    deals = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_benchmark(num_deals=deals)
