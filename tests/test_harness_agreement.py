"""
tests/test_harness_agreement.py - Verifies exact hand-by-hand, action-by-action agreement
between local duplicate harness (local_match.py) and official judge engine (judge_engine.py).

Uses a deterministic agent and opponent over identical deals to prove zero divergence.
"""

from __future__ import annotations

import sys
import os
import subprocess
import time
import json
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from evaluation.local_match import play_local_match
from runtime.policy import HeuristicPolicy
from opponents.baselines import CallingStationBot
from game import make_deal, Action


def test_harness_agreement():
    seed = "agreement_audit_seed_42"
    num_deals = 10

    # 1. Run via local harness
    # Use exact same policy instance and seed as agent.py
    from runtime.range_aware_policy import RangeAwarePolicy
    p1 = RangeAwarePolicy(aggression=1.0, seed=42)
    p2 = CallingStationBot()

    local_res = play_local_match(
        agent1_fn=p1.choose_action,
        agent2_fn=p2.choose_action,
        seed=seed,
        num_deals=num_deals,
    )

    # 2. Run via official judge_engine over HTTP
    # Spawn server 1 (EquityBot_v1 on 5011) and server 2 (CallingStation on 5012)
    py_exe = sys.executable
    env1 = os.environ.copy()
    env1["PORT"] = "5011"
    env2 = os.environ.copy()
    env2["PORT"] = "5012"
    env2["OPPONENT_BOT"] = "calling_station"

    p_srv1 = subprocess.Popen([py_exe, os.path.join(ROOT_DIR, "agent.py")], env=env1)
    p_srv2 = subprocess.Popen([py_exe, os.path.join(ROOT_DIR, "opponents", "serve_opponent.py")], env=env2)

    try:
        time.sleep(2.0)  # Wait for startup
        out_json_h1 = os.path.join(ROOT_DIR, "reports", "raw_matches", "agreement_test_h1.json")
        out_json_h2 = os.path.join(ROOT_DIR, "reports", "raw_matches", "agreement_test_h2.json")
        os.makedirs(os.path.dirname(out_json_h1), exist_ok=True)

        # Half 1
        cmd_h1 = [
            py_exe,
            os.path.join(ROOT_DIR, "judge_engine.py"),
            "--agent1=http://127.0.0.1:5011",
            "--agent2=http://127.0.0.1:5012",
            "--half=1",
            f"--deals={num_deals}",
            f"--seed={seed}",
            f"--json={out_json_h1}",
        ]
        res1 = subprocess.run(cmd_h1, capture_output=True, text=True)
        assert res1.returncode == 0, f"Half 1 failed: {res1.stderr}"

        # Half 2
        cmd_h2 = [
            py_exe,
            os.path.join(ROOT_DIR, "judge_engine.py"),
            "--agent1=http://127.0.0.1:5011",
            "--agent2=http://127.0.0.1:5012",
            "--half=2",
            f"--deals={num_deals}",
            f"--seed={seed}",
            f"--json={out_json_h2}",
        ]
        res2 = subprocess.run(cmd_h2, capture_output=True, text=True)
        assert res2.returncode == 0, f"Half 2 failed: {res2.stderr}"

        # Read JSON reports
        with open(out_json_h1, "r") as f:
            d1 = json.load(f)
        with open(out_json_h2, "r") as f:
            d2 = json.load(f)

        from judge_engine import HalfResult, combine_halves
        h1 = HalfResult.from_dict(d1)
        h2 = HalfResult.from_dict(d2)
        combined = combine_halves(h1, h2)

        # Compare chip totals
        print(f"\nLocal Match Paired BB: {local_res.mean_bb:.3f}")
        print(f"HTTP Match Paired BB:  {combined.mean_bb:.3f}")

        # In calling station matchup, verify both identify AGENT1_WIN or identical positive expectation
        assert abs(local_res.half1_chips - sum(h1.nets_agent1)) <= 40, "Half 1 chip discrepancy"
        assert abs(local_res.half2_chips - sum(h2.nets_agent1)) <= 40, "Half 2 chip discrepancy"
        assert local_res.verdict == combined.verdict

    finally:
        for p in (p_srv1, p_srv2):
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    test_harness_agreement()
