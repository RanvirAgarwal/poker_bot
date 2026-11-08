"""
evaluation/run_docker_qualification.py - Comprehensive qualification suite for Counterplay_v3.

Executes:
1. Docker qualification (9 matches, 18,000 hands) against pinned Timecasters, TwoStack, and vsmBOT
   under restricted container conditions (1 CPU, 4 GB RAM, read-only FS, tmpfs 512m).
2. Paired comparative baseline (9 matches, 18,000 hands) running DrawAware_v1 against the same
   pinned opponents on the same seeds.
3. Broader style evaluation (4 matches, 8,000 hands) against passive (check_fold), calling station,
   random, and aggressive (always_raise).

Records all metrics: verdicts, points, bb/deal, 95% CIs, time bank consumption, errors, exceptions,
and paired delta.
"""

from __future__ import annotations

import os
import sys
import json
import time
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.run_full_tournament_match import run_full_duplicate_match
from judge_engine import MatchResult


SEEDS = [
    "docker_val_20261108_01",
    "docker_val_20261108_02",
    "docker_val_20261108_03",
]

EXTERNAL_OPPONENTS = {
    "timecasters": os.path.join(ROOT_DIR, "opponents_external", "timecasters", "agent.py"),
    "twostack": os.path.join(ROOT_DIR, "opponents_external", "twostack", "agent.py"),
    "vsm": os.path.join(ROOT_DIR, "opponents_external", "vsm", "agent.py"),
}

BROADER_STYLES = [
    "check_fold",
    "calling_station",
    "random",
    "always_raise",
]


def extract_match_metrics(match_res: Any, match_id: str, outdir: str) -> Dict[str, Any]:
    match_json_path = os.path.join(outdir, f"{match_id}_match.json")
    with open(match_json_path, "r", encoding="utf-8") as f:
        d = json.load(f)

    h1_path = os.path.join(outdir, f"{match_id}_half1.json")
    h2_path = os.path.join(outdir, f"{match_id}_half2.json")
    
    h1_info = {}
    h2_info = {}
    if os.path.exists(h1_path):
        with open(h1_path, "r", encoding="utf-8") as f:
            d1 = json.load(f)
            h1_info = d1.get("agent1_info", {})
    if os.path.exists(h2_path):
        with open(h2_path, "r", encoding="utf-8") as f:
            d2 = json.load(f)
            h2_info = d2.get("agent1_info", {})

    int_exc = h1_info.get("internal_exceptions", 0) + h2_info.get("internal_exceptions", 0)
    fallbacks = h1_info.get("illegal_action_fallbacks", 0) + h2_info.get("illegal_action_fallbacks", 0)

    pts = d.get("points", {}).get("agent1", 0.0)
    net_chips = d.get("half_totals_chips", {}).get("half1", {}).get("agent1", 0) + \
                d.get("half_totals_chips", {}).get("half2", {}).get("agent1", 0)
    ci = d.get("ci", [0.0, 0.0])
    a1_stats = d.get("agent_stats", {}).get("agent1", [{}, {}])
    h1_stats = a1_stats[0] if len(a1_stats) > 0 else {}
    h2_stats = a1_stats[1] if len(a1_stats) > 1 else {}

    return {
        "verdict": d.get("verdict", "UNKNOWN"),
        "points": pts,
        "deals": d.get("num_deals", 1000),
        "net_chips": net_chips,
        "bb_per_deal": d.get("mean_bb_per_deal", 0.0),
        "std": d.get("std_bb", 0.0),
        "stderr": d.get("stderr_bb", 0.0),
        "ci_low": ci[0],
        "ci_high": ci[1],
        "h1_thinking_sec": h1_stats.get("time_seconds", 0.0),
        "h1_wall_sec": h1_stats.get("wall_seconds", 0.0),
        "h1_calls": h1_stats.get("calls", 0),
        "h1_errors": h1_stats.get("errors", 0),
        "h2_thinking_sec": h2_stats.get("time_seconds", 0.0),
        "h2_wall_sec": h2_stats.get("wall_seconds", 0.0),
        "h2_calls": h2_stats.get("calls", 0),
        "h2_errors": h2_stats.get("errors", 0),
        "internal_exceptions": int_exc,
        "illegal_fallbacks": fallbacks,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="all", choices=["all", "1", "2", "3", "p1", "p2", "p3"])
    args = parser.parse_args()

    outdir = os.path.join(ROOT_DIR, "reports", "raw_matches")
    os.makedirs(outdir, exist_ok=True)
    res_json_path = os.path.join(ROOT_DIR, "reports", "docker_qualification_results.json")
    
    if os.path.exists(res_json_path):
        try:
            with open(res_json_path, "r", encoding="utf-8") as f:
                results_record = json.load(f)
        except Exception:
            results_record = {}
    else:
        results_record = {}

    results_record["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    results_record["docker_image"] = "poker-agent-check:latest"
    if "container_qualification" not in results_record:
        results_record["container_qualification"] = {}
    if "drawaware_baseline" not in results_record:
        results_record["drawaware_baseline"] = {}
    if "broader_styles" not in results_record:
        results_record["broader_styles"] = {}
    if "paired_deltas" not in results_record:
        results_record["paired_deltas"] = {}

    print("=" * 80)
    print(f"STARTING QUALIFICATION & BENCHMARK SUITE (PHASE: {args.phase})")
    print("=" * 80)

    # -------------------------------------------------------------
    # 1. DOCKER QUALIFICATION OF COUNTERPLAY_V3
    # -------------------------------------------------------------
    if args.phase in ("all", "1", "p1"):
        print("\n" + "=" * 80)
        print("PHASE 1: DOCKER RESTRICTED CONTAINER QUALIFICATION (Counterplay_v3)")
        print("=" * 80)

        for opp_name, opp_script in EXTERNAL_OPPONENTS.items():
            if opp_name not in results_record["container_qualification"]:
                results_record["container_qualification"][opp_name] = {}
            for seed in SEEDS:
                match_id = f"docker_val_Counterplay_v3_{opp_name}_{seed}"
                saved_match = os.path.join(outdir, f"{match_id}_match.json")
                if os.path.exists(saved_match):
                    print(f"\n>>> Loading cached Container Match: {match_id}")
                    metrics = extract_match_metrics(None, match_id, outdir)
                    metrics["elapsed_sec"] = 0.0
                    results_record["container_qualification"][opp_name][seed] = metrics
                else:
                    print(f"\n>>> Running Container Match: Counterplay_v3 vs {opp_name} (seed: {seed})")
                    t0 = time.time()
                    res = run_full_duplicate_match(
                        agent1_script="poker-agent-check:latest",
                        agent2_script=opp_script,
                        deals=1000,
                        seed=seed,
                        output_dir=outdir,
                        use_container=True,
                        match_id=match_id,
                    )
                    elapsed = time.time() - t0
                    metrics = extract_match_metrics(res, match_id, outdir)
                    metrics["elapsed_sec"] = elapsed
                    results_record["container_qualification"][opp_name][seed] = metrics
                with open(res_json_path, "w", encoding="utf-8") as f:
                    json.dump(results_record, f, indent=2)
                print(f">>> Result: {metrics['verdict']} ({metrics['points']} pts), {metrics['bb_per_deal']:+.3f} bb/deal, CI: [{metrics['ci_low']:+.2f}, {metrics['ci_high']:+.2f}], Bank: h1={metrics['h1_thinking_sec']:.2f}s, h2={metrics['h2_thinking_sec']:.2f}s, elapsed={metrics['elapsed_sec']:.1f}s")

    # -------------------------------------------------------------
    # 2. MATCHED BASELINE: DRAWAWARE_V1
    # -------------------------------------------------------------
    if args.phase in ("all", "2", "p2"):
        print("\n" + "=" * 80)
        print("PHASE 2: MATCHED BASELINE EVALUATION (DrawAware_v1)")
        print("=" * 80)

        drawaware_script = os.path.join(ROOT_DIR, "opponents", "agent_drawaware_v1.py")
        for opp_name, opp_script in EXTERNAL_OPPONENTS.items():
            if opp_name not in results_record["drawaware_baseline"]:
                results_record["drawaware_baseline"][opp_name] = {}
            for seed in SEEDS:
                match_id = f"docker_val_DrawAware_v1_{opp_name}_{seed}"
                saved_match = os.path.join(outdir, f"{match_id}_match.json")
                if os.path.exists(saved_match):
                    print(f"\n>>> Loading cached Baseline Match: {match_id}")
                    metrics = extract_match_metrics(None, match_id, outdir)
                    metrics["elapsed_sec"] = 0.0
                    results_record["drawaware_baseline"][opp_name][seed] = metrics
                else:
                    print(f"\n>>> Running Matched Baseline: DrawAware_v1 vs {opp_name} (seed: {seed})")
                    t0 = time.time()
                    res = run_full_duplicate_match(
                        agent1_script=drawaware_script,
                        agent2_script=opp_script,
                        deals=1000,
                        seed=seed,
                        output_dir=outdir,
                        use_container=False,
                        match_id=match_id,
                    )
                    elapsed = time.time() - t0
                    metrics = extract_match_metrics(res, match_id, outdir)
                    metrics["elapsed_sec"] = elapsed
                    results_record["drawaware_baseline"][opp_name][seed] = metrics
                with open(res_json_path, "w", encoding="utf-8") as f:
                    json.dump(results_record, f, indent=2)
                print(f">>> Result: {metrics['verdict']} ({metrics['points']} pts), {metrics['bb_per_deal']:+.3f} bb/deal, CI: [{metrics['ci_low']:+.2f}, {metrics['ci_high']:+.2f}], Bank: h1={metrics['h1_thinking_sec']:.2f}s, h2={metrics['h2_thinking_sec']:.2f}s, elapsed={metrics['elapsed_sec']:.1f}s")

    # -------------------------------------------------------------
    # 3. BROADER STYLES EVALUATION
    # -------------------------------------------------------------
    if args.phase in ("all", "3", "p3"):
        print("\n" + "=" * 80)
        print("PHASE 3: BROADER STYLE EVALUATION (Counterplay_v3)")
        print("=" * 80)

        serve_opp_script = os.path.join(ROOT_DIR, "opponents", "serve_opponent.py")
        style_seed = "docker_val_20261108_01"
        for style in BROADER_STYLES:
            match_id = f"docker_val_Counterplay_v3_style_{style}"
            saved_match = os.path.join(outdir, f"{match_id}_match.json")
            if os.path.exists(saved_match):
                print(f"\n>>> Loading cached Broader Style Match: {match_id}")
                metrics = extract_match_metrics(None, match_id, outdir)
                metrics["elapsed_sec"] = 0.0
                results_record["broader_styles"][style] = metrics
            else:
                print(f"\n>>> Running Broader Style Match: Counterplay_v3 vs {style}")
                t0 = time.time()
                res = run_full_duplicate_match(
                    agent1_script="poker-agent-check:latest",
                    agent2_script=serve_opp_script,
                    deals=1000,
                    seed=style_seed,
                    output_dir=outdir,
                    opp_bot=style,
                    use_container=True,
                    match_id=match_id,
                )
                elapsed = time.time() - t0
                metrics = extract_match_metrics(res, match_id, outdir)
                metrics["elapsed_sec"] = elapsed
                results_record["broader_styles"][style] = metrics
            with open(res_json_path, "w", encoding="utf-8") as f:
                json.dump(results_record, f, indent=2)
            print(f">>> Result: {metrics['verdict']} ({metrics['points']} pts), {metrics['bb_per_deal']:+.3f} bb/deal, CI: [{metrics['ci_low']:+.2f}, {metrics['ci_high']:+.2f}], elapsed={metrics['elapsed_sec']:.1f}s")

    # -------------------------------------------------------------
    # 4. COMPUTE PAIRED DELTAS & AGGREGATES
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("COMPUTING PAIRED DELTAS & FINAL SUMMARY")
    print("=" * 80)

    paired_deltas = {}
    for opp_name in EXTERNAL_OPPONENTS:
        paired_deltas[opp_name] = {}
        for seed in SEEDS:
            cp_data = results_record.get("container_qualification", {}).get(opp_name, {}).get(seed)
            da_data = results_record.get("drawaware_baseline", {}).get(opp_name, {}).get(seed)
            if cp_data and da_data:
                cp_bb = cp_data["bb_per_deal"]
                da_bb = da_data["bb_per_deal"]
                delta = cp_bb - da_bb
                paired_deltas[opp_name][seed] = {
                    "counterplay_bb": cp_bb,
                    "drawaware_bb": da_bb,
                    "delta_bb": delta,
                }
    results_record["paired_deltas"] = paired_deltas

    # Save complete JSON
    with open(res_json_path, "w", encoding="utf-8") as f:
        json.dump(results_record, f, indent=2)
    print(f"\nSaved qualification results to: {res_json_path}")


if __name__ == "__main__":
    main()
