"""
evaluation/compare_continuation_filter.py - Controlled 1,000-Deal Duplicate Study
comparing RangeAware_v2_WithFilter vs RangeAware_v2_NoFilter.

Both candidates hold every other setting strictly identical:
- Street-specific Bayesian aggression tracking (pf_rate, post_rate)
- Protected check-trapping (20% OOP with Cat >= 5 on flop/turn)
- Mixed value sizing (65% pot / 35% half-pot)
- 80 Monte Carlo sampling budget per postflop decision
- Identical random seeds and initial parameters

Runs repeated 1,000-deal duplicate matches with matched seeds across standard
and adversarial opponents, plus reserved unseen opponents and seeds for final selection.
"""

from __future__ import annotations

import sys
import os
import json
import time
import math
import statistics
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match
from runtime.range_aware_policy import RangeAwarePolicy
from opponents.baselines import BASELINE_REGISTRY
from opponents.adversarial import ADVERSARIAL_REGISTRY

ALL_OPPONENTS = {**BASELINE_REGISTRY, **ADVERSARIAL_REGISTRY}

PRIMARY_OPPONENTS = [
    # Standard baselines
    "action_conditioned_range",
    "calling_station",
    "always_raise",
    "size_aware_equity",
    # Adversarial stress opponents
    "street_inversion_attacker",
    "check_trap_attacker",
    "river_bluff_attacker",
    "fold_bully_attacker",
]

PRIMARY_SEEDS = ["seed_cf_101", "seed_cf_202", "seed_cf_303"]

RESERVE_OPPONENTS = [
    "trained_response_bot",
    "sizing_tell_disguiser",
    "threshold_attacker_below",
]

RESERVE_SEEDS = ["final_val_777", "final_val_888", "final_val_999"]


def _run_single_match(args: Tuple[str, bool, str, str, int]) -> Dict[str, Any]:
    candidate_name, use_filter, opp_name, seed, num_deals = args
    opp_cls = ALL_OPPONENTS[opp_name]
    opp_bot = opp_cls()
    cand_policy = RangeAwarePolicy(aggression=1.0, seed=42, use_continuation_filter=use_filter)

    opp_new_half = getattr(opp_bot, "new_half", None)
    opp_on_end = getattr(opp_bot, "on_hand_end", None)

    t0 = time.perf_counter()
    res = play_local_match(
        agent1_fn=cand_policy.choose_action,
        agent2_fn=opp_bot.choose_action,
        seed=seed,
        num_deals=num_deals,
        agent1_new_half_fn=None,
        agent2_new_half_fn=opp_new_half,
        agent1_end_fn=None,
        agent2_end_fn=opp_on_end,
        keep_logs=False,
    )
    elapsed = time.perf_counter() - t0

    if res.verdict == "AGENT1_WIN":
        pts = 1.0
    elif res.verdict == "CHOP":
        pts = 0.5
    else:
        pts = 0.0

    return {
        "candidate": candidate_name,
        "use_continuation_filter": use_filter,
        "opponent": opp_name,
        "seed": seed,
        "num_deals": num_deals,
        "mean_bb": res.mean_bb,
        "std_bb": res.std_bb,
        "stderr_bb": res.stderr_bb,
        "ci_lower": res.ci[0],
        "ci_upper": res.ci[1],
        "verdict": res.verdict,
        "points": pts,
        "half1_chips": res.half1_chips,
        "half2_chips": res.half2_chips,
        "total_chips": res.half1_chips + res.half2_chips,
        "agent1_errors": res.agent1_errors,
        "agent2_errors": res.agent2_errors,
        "elapsed_seconds": round(elapsed, 3),
    }


def run_experiment_suite(num_deals: int = 1000, max_workers: int = 4):
    print("=" * 80)
    print("CONTROLLED CONTINUATION FILTER STUDY (1,000 DEALS PER MATCH)")
    print(f"Num Deals per Match: {num_deals} (duplicate = {num_deals * 2} hands)")
    print("Candidate A: RangeAware_v2_NoFilter   (use_continuation_filter=False)")
    print("Candidate B: RangeAware_v2_WithFilter (use_continuation_filter=True)")
    print("=" * 80)

    # 1. Primary evaluation jobs
    primary_jobs = []
    for opp in PRIMARY_OPPONENTS:
        for seed in PRIMARY_SEEDS:
            primary_jobs.append(("RangeAware_v2_NoFilter", False, opp, seed, num_deals))
            primary_jobs.append(("RangeAware_v2_WithFilter", True, opp, seed, num_deals))

    print(f"\n[1/2] Running Primary Study: {len(primary_jobs)} total matches ({len(PRIMARY_OPPONENTS)} opps x {len(PRIMARY_SEEDS)} seeds x 2 candidates)...")
    t_start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        primary_results = list(executor.map(_run_single_match, primary_jobs))
    t_primary = time.perf_counter() - t_start
    print(f"Completed {len(primary_jobs)} matches in {t_primary:.1f}s ({t_primary / len(primary_jobs):.2f}s per 1000-deal match)")

    # 2. Reserve validation jobs (for final selection)
    reserve_jobs = []
    for opp in RESERVE_OPPONENTS:
        for seed in RESERVE_SEEDS:
            reserve_jobs.append(("RangeAware_v2_NoFilter", False, opp, seed, num_deals))
            reserve_jobs.append(("RangeAware_v2_WithFilter", True, opp, seed, num_deals))

    print(f"\n[2/2] Running Reserve Final Selection Suite: {len(reserve_jobs)} matches ({len(RESERVE_OPPONENTS)} opps x {len(RESERVE_SEEDS)} seeds x 2 candidates)...")
    t_start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        reserve_results = list(executor.map(_run_single_match, reserve_jobs))
    t_reserve = time.perf_counter() - t_start
    print(f"Completed {len(reserve_jobs)} reserve matches in {t_reserve:.1f}s")

    all_results = primary_results + reserve_results

    # Save raw records
    out_dir = os.path.join(ROOT_DIR, "reports", "raw_matches")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "continuation_filter_study.json")
    with open(out_path, "w") as f:
        json.dump({
            "metadata": {
                "num_deals": num_deals,
                "primary_opponents": PRIMARY_OPPONENTS,
                "primary_seeds": PRIMARY_SEEDS,
                "reserve_opponents": RESERVE_OPPONENTS,
                "reserve_seeds": RESERVE_SEEDS,
                "total_matches": len(all_results),
            },
            "primary_matches": primary_results,
            "reserve_matches": reserve_results,
        }, f, indent=2)
    print(f"\nSaved raw results to {out_path}")

    # Generate and print summary tables
    _summarize_results("PRIMARY 1,000-DEAL STUDY", primary_results)
    _summarize_results("RESERVE VALIDATION SUITE", reserve_results)
    _summarize_combined("COMBINED BENCHMARK TOTALS", all_results)


def _summarize_results(title: str, results: List[Dict[str, Any]]):
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)

    by_cand: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_cand.setdefault(r["candidate"], []).append(r)

    print(f"{'Candidate':<28} | {'Matches':<7} | {'Points':<10} | {'Win Rate':<8} | {'Mean BB/deal':<14} | {'Total Chips':<12} | {'Time/Match'}")
    print("-" * 90)

    for cand, c_res in by_cand.items():
        n_matches = len(c_res)
        total_pts = sum(r["points"] for r in c_res)
        wins = sum(1 for r in c_res if r["verdict"] == "AGENT1_WIN")
        chops = sum(1 for r in c_res if r["verdict"] == "CHOP")
        losses = sum(1 for r in c_res if r["verdict"] == "AGENT2_WIN")
        mean_bb = statistics.mean(r["mean_bb"] for r in c_res)
        stdev_bb = statistics.stdev(r["mean_bb"] for r in c_res) if n_matches > 1 else 0.0
        tot_chips = sum(r["total_chips"] for r in c_res)
        avg_time = statistics.mean(r["elapsed_seconds"] for r in c_res)

        print(f"{cand:<28} | {n_matches:<7} | {total_pts:.1f}/{n_matches:<5} | {wins}W/{chops}C/{losses}L | {mean_bb:>+6.3f} +/- {stdev_bb:>5.2f} | {tot_chips:>+11,d} | {avg_time:>5.2f}s")

    # Detailed head-to-head opponent breakdown
    print("\n  Per-Opponent Mean BB/deal Comparison (matched seeds):")
    print(f"  {'Opponent':<28} | {'NoFilter (Mean BB)':<20} | {'WithFilter (Mean BB)':<20} | {'Delta (With - No)'}")
    print("  " + "-" * 80)

    opponents = sorted(list({r["opponent"] for r in results}))
    for opp in opponents:
        no_filter_bbs = [r["mean_bb"] for r in results if r["opponent"] == opp and not r["use_continuation_filter"]]
        with_filter_bbs = [r["mean_bb"] for r in results if r["opponent"] == opp and r["use_continuation_filter"]]
        m_no = statistics.mean(no_filter_bbs)
        m_wi = statistics.mean(with_filter_bbs)
        delta = m_wi - m_no
        print(f"  {opp:<28} | {m_no:>+18.3f} | {m_wi:>+18.3f} | {delta:>+16.3f}")


def _summarize_combined(title: str, results: List[Dict[str, Any]]):
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)

    by_cand: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_cand.setdefault(r["candidate"], []).append(r)

    print(f"{'Candidate':<28} | {'Matches':<7} | {'Points':<10} | {'Win Rate':<8} | {'Mean BB/deal':<14} | {'Total Chips':<12} | {'Errors'}")
    print("-" * 90)

    for cand, c_res in by_cand.items():
        n_matches = len(c_res)
        total_pts = sum(r["points"] for r in c_res)
        wins = sum(1 for r in c_res if r["verdict"] == "AGENT1_WIN")
        chops = sum(1 for r in c_res if r["verdict"] == "CHOP")
        losses = sum(1 for r in c_res if r["verdict"] == "AGENT2_WIN")
        mean_bb = statistics.mean(r["mean_bb"] for r in c_res)
        stdev_bb = statistics.stdev(r["mean_bb"] for r in c_res) if n_matches > 1 else 0.0
        tot_chips = sum(r["total_chips"] for r in c_res)
        tot_errs = sum(r["agent1_errors"] for r in c_res)

        print(f"{cand:<28} | {n_matches:<7} | {total_pts:.1f}/{n_matches:<5} | {wins}W/{chops}C/{losses}L | {mean_bb:>+6.3f} +/- {stdev_bb:>5.2f} | {tot_chips:>+11,d} | {tot_errs}")


if __name__ == "__main__":
    run_experiment_suite(num_deals=1000, max_workers=4)
