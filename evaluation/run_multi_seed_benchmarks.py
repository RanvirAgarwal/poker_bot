"""
evaluation/run_multi_seed_benchmarks.py - Multi-seed full-length duplicate match runner.

Runs independent seeds across opponents, recording exact paired BB, CI, and judge JSONs.
"""

from __future__ import annotations

import sys
import os
import argparse
from typing import List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.run_full_tournament_match import run_full_duplicate_match
from judge_engine import MatchResult


def run_multi_seed_evaluation(
    agent1_script: str = "agent.py",
    agent2_script: str = "starter/baseline-bots/baseline_calling_station.py",
    seeds: List[str] = None,
    deals: int = 1000,
    output_dir: str = "reports/raw_matches",
):
    if seeds is None:
        seeds = [f"official_seed_{i}" for i in range(1, 6)]

    print("=" * 80)
    print(f"MULTI-SEED FULL DUPLICATE EVALUATION: {len(seeds)} matches ({deals} deals each)")
    print(f"Agent 1: {agent1_script}")
    print(f"Agent 2: {agent2_script}")
    print(f"Seeds: {seeds}")
    print("=" * 80)

    results: List[MatchResult] = []
    for s in seeds:
        print(f"\n>>> Running Match for Seed: {s} <<<")
        res = run_full_duplicate_match(
            agent1_script=os.path.abspath(agent1_script),
            agent2_script=os.path.abspath(agent2_script),
            deals=deals,
            seed=s,
            output_dir=output_dir,
        )
        results.append(res)

    print("\n" + "=" * 80)
    print("MULTI-SEED EVALUATION SUMMARY")
    print("=" * 80)
    print(f"{'Seed':<18} | {'Verdict':<12} | {'Mean BB/deal':<14} | {'95% CI':<22} | {'Half1 Time':<10} | {'Half2 Time':<10}")
    print("-" * 92)

    total_points_a1 = 0.0
    for res in results:
        total_points_a1 += res.points.get("agent1", 0.0)
        ci_str = f"[{res.ci[0]:+.2f}, {res.ci[1]:+.2f}]"
        t1 = f"{res.agent_stats['agent1'][0].time_seconds:.2f}s"
        t2 = f"{res.agent_stats['agent1'][1].time_seconds:.2f}s"
        print(f"{res.match_seed:<18} | {res.verdict:<12} | {res.mean_bb:+10.3f}   | {ci_str:<22} | {t1:<10} | {t2:<10}")

    print("-" * 92)
    print(f"Total Matches: {len(results)} | Total Agent 1 Points: {total_points_a1} / {len(results)} ({total_points_a1/len(results)*100:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent1", default="agent.py")
    parser.add_argument("--agent2", default="starter/baseline-bots/baseline_calling_station.py")
    parser.add_argument("--deals", type=int, default=1000)
    parser.add_argument("--num-seeds", type=int, default=5)
    args = parser.parse_args()

    seeds = [f"tourn_seed_{i}" for i in range(1, args.num_seeds + 1)]
    run_multi_seed_evaluation(args.agent1, args.agent2, seeds=seeds, deals=args.deals)

