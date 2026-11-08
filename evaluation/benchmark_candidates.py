"""
evaluation/benchmark_candidates.py - Rigorous, side-by-side evaluation of EquityBot_v1 vs RangeAware_v2 across the complete 12-opponent suite.

Key requirements:
- Matched seeds across candidates for exact paired fairness.
- Automated summarization via summary_table.py.
- Export of raw JSON match records to reports/raw_matches/.
- Head-to-head match between EquityBot_v1 and RangeAware_v2.
"""

from __future__ import annotations

import sys
import os
import json
import time
from typing import Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match, format_local_result
from evaluation.summary_table import summarize_results, format_markdown_table
from runtime.policy import HeuristicPolicy
from runtime.range_aware_policy import RangeAwarePolicy
from opponents.baselines import BASELINE_REGISTRY

RAW_MATCH_DIR = os.path.join(ROOT_DIR, "reports", "raw_matches")
os.makedirs(RAW_MATCH_DIR, exist_ok=True)


def run_benchmark(num_deals: int = 100, seed_base: str = "eval_seed"):
    print("=" * 80)
    print(f"BENCHMARK: EquityBot_v1 vs RangeAware_v2 ({num_deals} duplicate deals per match)")
    print(f"Seed base: {seed_base}")
    print("=" * 80)

    p_equity = HeuristicPolicy(aggression=1.0, seed=42)
    p_range = RangeAwarePolicy(aggression=1.0, seed=42)

    # 1. Direct Head-to-Head
    print("\n" + "=" * 50)
    print("1. DIRECT HEAD-TO-HEAD: EquityBot_v1 vs RangeAware_v2")
    print("=" * 50)
    t0 = time.time()
    h2h_res = play_local_match(
        agent1_fn=p_range.choose_action,
        agent2_fn=p_equity.choose_action,
        seed=f"{seed_base}_range_vs_equity",
        num_deals=num_deals,
    )
    t_h2h = time.time() - t0
    h2h_res.elapsed_seconds = t_h2h

    h2h_json_path = os.path.join(RAW_MATCH_DIR, f"h2h_RangeAware_v2_vs_EquityBot_v1_{num_deals}deals.json")
    with open(h2h_json_path, "w") as f:
        json.dump({
            "candidate1": "RangeAware_v2",
            "candidate2": "EquityBot_v1",
            "num_deals": num_deals,
            "seed": f"{seed_base}_range_vs_equity",
            "mean_bb": h2h_res.mean_bb,
            "ci": list(h2h_res.ci),
            "std_bb": h2h_res.std_bb,
            "verdict": h2h_res.verdict,
            "elapsed_seconds": t_h2h,
            "paired_diffs": h2h_res.paired_bb,
        }, f, indent=2)

    print(format_local_result(h2h_res, name1="RangeAware_v2", name2="EquityBot_v1"))
    print(f"Saved raw H2H JSON to: {h2h_json_path}")

    # 2. Benchmark RangeAware_v2 vs Complete 12-Opponent Suite
    print("\n" + "=" * 50)
    print(f"2. RANGEAWARE_V2 VS 12 OPPONENTS ({num_deals} deals)")
    print("=" * 50)
    range_results = {}
    for opp_name, opp_cls in BASELINE_REGISTRY.items():
        opp_inst = opp_cls()
        t_start = time.time()
        res = play_local_match(
            agent1_fn=p_range.choose_action,
            agent2_fn=opp_inst.choose_action,
            seed=f"{seed_base}_{opp_name}",
            num_deals=num_deals,
        )
        res.elapsed_seconds = time.time() - t_start
        range_results[opp_name] = res

        # Save individual raw match
        json_path = os.path.join(RAW_MATCH_DIR, f"RangeAware_v2_vs_{opp_name}_{num_deals}deals.json")
        with open(json_path, "w") as f:
            json.dump({
                "candidate": "RangeAware_v2",
                "opponent": opp_name,
                "num_deals": num_deals,
                "seed": f"{seed_base}_{opp_name}",
                "mean_bb": res.mean_bb,
                "ci": list(res.ci),
                "std_bb": res.std_bb,
                "verdict": res.verdict,
                "elapsed_seconds": res.elapsed_seconds,
            }, f, indent=2)

        ci_str = f"[{res.ci[0]:+.2f}, {res.ci[1]:+.2f}]"
        print(f"vs {opp_name:<24} | {res.verdict:<12} | {res.mean_bb:+8.2f} bb/deal | {ci_str:<18} ({res.elapsed_seconds:.2f}s)")

    # 3. Benchmark EquityBot_v1 vs Complete 12-Opponent Suite (Matched Seeds)
    print("\n" + "=" * 50)
    print(f"3. EQUITYBOT_V1 VS 12 OPPONENTS ({num_deals} deals)")
    print("=" * 50)
    equity_results = {}
    for opp_name, opp_cls in BASELINE_REGISTRY.items():
        opp_inst = opp_cls()
        t_start = time.time()
        res = play_local_match(
            agent1_fn=p_equity.choose_action,
            agent2_fn=opp_inst.choose_action,
            seed=f"{seed_base}_{opp_name}",
            num_deals=num_deals,
        )
        res.elapsed_seconds = time.time() - t_start
        equity_results[opp_name] = res

        # Save individual raw match
        json_path = os.path.join(RAW_MATCH_DIR, f"EquityBot_v1_vs_{opp_name}_{num_deals}deals.json")
        with open(json_path, "w") as f:
            json.dump({
                "candidate": "EquityBot_v1",
                "opponent": opp_name,
                "num_deals": num_deals,
                "seed": f"{seed_base}_{opp_name}",
                "mean_bb": res.mean_bb,
                "ci": list(res.ci),
                "std_bb": res.std_bb,
                "verdict": res.verdict,
                "elapsed_seconds": res.elapsed_seconds,
            }, f, indent=2)

        ci_str = f"[{res.ci[0]:+.2f}, {res.ci[1]:+.2f}]"
        print(f"vs {opp_name:<24} | {res.verdict:<12} | {res.mean_bb:+8.2f} bb/deal | {ci_str:<18} ({res.elapsed_seconds:.2f}s)")

    # 4. Generate Verified Markdown Tables
    print("\n" + "=" * 50)
    print("4. VERIFIED BENCHMARK TABLES")
    print("=" * 50)
    range_summaries = summarize_results(range_results)
    equity_summaries = summarize_results(equity_results)

    print("\n" + format_markdown_table("RangeAware_v2", range_summaries))
    print("\n" + format_markdown_table("EquityBot_v1", equity_summaries))

    # 5. Direct Comparative Table
    print("\n### Side-by-Side Comparison: RangeAware_v2 vs EquityBot_v1")
    print("| Opponent | EquityBot_v1 Mean BB | RangeAware_v2 Mean BB | Delta (BB/deal) | EquityBot Verdict | RangeAware Verdict |")
    print("|:---|:---:|:---:|:---:|:---:|:---:|")
    for r_s, e_s in zip(range_summaries, equity_summaries):
        delta = r_s.mean_bb - e_s.mean_bb
        print(f"| `{r_s.opponent}` | {e_s.mean_bb:+.3f} | {r_s.mean_bb:+.3f} | {delta:+.3f} | {e_s.verdict} | {r_s.verdict} |")

    return h2h_res, range_results, equity_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--deals", type=int, default=100)
    parser.add_argument("--seed", type=str, default="milestone_c_eval")
    args = parser.parse_args()

    run_benchmark(num_deals=args.deals, seed_base=args.seed)
