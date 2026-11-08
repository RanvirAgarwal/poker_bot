"""
tests/test_harness_agreement.py - Verifies exact hand-by-hand, action-by-action agreement
between local duplicate harness (local_match.py) and official judge engine (judge_engine.py).

With controlled evaluation RNG streams and FRESH PROCESSES per half, compares:
1. Every hand's complete action sequence.
2. Every hand's net chip payoff.
3. Complete paired-result vector (paired_bb) element by element.
4. Exact sample mean, sample standard deviation (ddof=1), and 95% CI.
5. Final decisive tournament verdict.

Reports the exact first divergence if any occurs.
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

from evaluation.local_match import play_local_match_fresh
from runtime.counterplay_policy import CounterplayPolicy
from opponents.baselines import CallingStationBot
from judge_engine import HalfResult, combine_halves


def _start_server(py_exe: str, script: str, port: str, extra_env: dict | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    env["PORT"] = port
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen([py_exe, script], env=env)


def _kill_servers(*procs):
    for p in procs:
        if p is not None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass


def test_harness_agreement_exact():
    seed = "agreement_audit_seed_42"
    num_deals = 10
    py_exe = sys.executable

    # 1. Local execution with fresh policy per half matching agent.py (_POLICY = CounterplayPolicy)
    def make_p1():
        pol = CounterplayPolicy(seed=42)
        return pol.choose_action, pol.on_hand_end, None

    def make_p2():
        bot = CallingStationBot()
        return bot.choose_action, None, None

    local_res = play_local_match_fresh(
        make_agent1=make_p1,
        make_agent2=make_p2,
        seed=seed,
        num_deals=num_deals,
        keep_logs=True,
    )

    out_json_h1 = os.path.join(ROOT_DIR, "reports", "raw_matches", "agreement_test_h1.json")
    out_json_h2 = os.path.join(ROOT_DIR, "reports", "raw_matches", "agreement_test_h2.json")
    os.makedirs(os.path.dirname(out_json_h1), exist_ok=True)

    # 2. HTTP execution via judge_engine with FRESH server process per half
    # --- Half 1 ---
    srv1_h1 = _start_server(py_exe, os.path.join(ROOT_DIR, "agent.py"), "5011")
    srv2_h1 = _start_server(py_exe, os.path.join(ROOT_DIR, "opponents", "serve_opponent.py"), "5012", {"OPPONENT_BOT": "calling_station"})
    try:
        time.sleep(2.0)  # Wait for uvicorn binding
        cmd_h1 = [
            py_exe, os.path.join(ROOT_DIR, "judge_engine.py"),
            "--agent1=http://127.0.0.1:5011",
            "--agent2=http://127.0.0.1:5012",
            "--half=1",
            f"--deals={num_deals}",
            f"--seed={seed}",
            f"--json={out_json_h1}",
            "--logs",
        ]
        res1 = subprocess.run(cmd_h1, capture_output=True, text=True)
        assert res1.returncode == 0, f"Half 1 failed: {res1.stderr}"
    finally:
        _kill_servers(srv1_h1, srv2_h1)

    # --- Half 2 (Fresh server processes per tournament specification) ---
    time.sleep(0.5)
    srv1_h2 = _start_server(py_exe, os.path.join(ROOT_DIR, "agent.py"), "5011")
    srv2_h2 = _start_server(py_exe, os.path.join(ROOT_DIR, "opponents", "serve_opponent.py"), "5012", {"OPPONENT_BOT": "calling_station"})
    try:
        time.sleep(2.0)  # Wait for uvicorn binding
        cmd_h2 = [
            py_exe, os.path.join(ROOT_DIR, "judge_engine.py"),
            "--agent1=http://127.0.0.1:5011",
            "--agent2=http://127.0.0.1:5012",
            "--half=2",
            f"--deals={num_deals}",
            f"--seed={seed}",
            f"--json={out_json_h2}",
            "--logs",
        ]
        res2 = subprocess.run(cmd_h2, capture_output=True, text=True)
        assert res2.returncode == 0, f"Half 2 failed: {res2.stderr}"
    finally:
        _kill_servers(srv1_h2, srv2_h2)

    # Load HTTP results
    with open(out_json_h1, "r") as f:
        d1 = json.load(f)
    with open(out_json_h2, "r") as f:
        d2 = json.load(f)

    h1 = HalfResult.from_dict(d1)
    h2 = HalfResult.from_dict(d2)
    http_res = combine_halves(h1, h2)

    # --- A. Compare hand-by-hand logs for Half 1 and Half 2 ---
    for half_name, half_idx, http_half in (("half1", 1, h1), ("half2", 2, h2)):
        local_half_logs = local_res.logs[half_name]
        http_half_logs = http_half.logs

        assert len(local_half_logs) == len(http_half_logs) == num_deals

        for d in range(num_deals):
            loc_h = local_half_logs[d]
            htt_h = http_half_logs[d]

            # 1. Compare observations (cards dealt & button)
            if loc_h["hole_cards"] != htt_h["hole_cards"]:
                pytest.fail(
                    f"FIRST DIVERGENCE at Half {half_idx}, Deal {d}: "
                    f"Hole cards Local {loc_h['hole_cards']} != HTTP {htt_h['hole_cards']}"
                )
            if loc_h["board"] != htt_h["board"]:
                pytest.fail(
                    f"FIRST DIVERGENCE at Half {half_idx}, Deal {d}: "
                    f"Board Local {loc_h['board']} != HTTP {htt_h['board']}"
                )
            if loc_h["button_seat"] != htt_h["button_seat"]:
                pytest.fail(
                    f"FIRST DIVERGENCE at Half {half_idx}, Deal {d}: "
                    f"Button Local {loc_h['button_seat']} != HTTP {htt_h['button_seat']}"
                )

            # 2. Compare net chips for the hand
            if loc_h["nets"] != htt_h["nets"]:
                pytest.fail(
                    f"FIRST DIVERGENCE at Half {half_idx}, Deal {d}: "
                    f"Local nets {loc_h['nets']} != HTTP nets {htt_h['nets']}"
                )

            # 3. Compare exact action sequences
            loc_acts = [(a["street"], a["action"], a["amount"]) for a in loc_h["actions"]]
            htt_acts = [(a["street"], a["action"], a["amount"]) for a in htt_h["actions"]]
            if loc_acts != htt_acts:
                pytest.fail(
                    f"FIRST DIVERGENCE at Half {half_idx}, Deal {d}: "
                    f"Local actions {loc_acts} != HTTP actions {htt_acts}"
                )

    # --- B. Compare paired_bb vector element-by-element ---
    assert len(local_res.paired_bb) == len(http_res.paired_bb) == num_deals
    for d in range(num_deals):
        diff = abs(local_res.paired_bb[d] - http_res.paired_bb[d])
        if diff > 1e-6:
            pytest.fail(
                f"FIRST DIVERGENCE in paired_bb vector at deal {d}: "
                f"Local {local_res.paired_bb[d]} != HTTP {http_res.paired_bb[d]}"
            )

    # --- C. Compare aggregate metrics ---
    assert abs(local_res.mean_bb - http_res.mean_bb) < 1e-6
    assert abs(local_res.std_bb - http_res.std_bb) < 1e-6
    assert abs(local_res.stderr_bb - http_res.stderr_bb) < 1e-6
    assert abs(local_res.ci[0] - http_res.ci[0]) < 1e-6
    assert abs(local_res.ci[1] - http_res.ci[1]) < 1e-6
    assert local_res.verdict == http_res.verdict

    print(f"\n[OK] EXACT AGREEMENT VERIFIED across {num_deals} duplicate deals (20 hands total) with FRESH PROCESSES per half!")
    print(f"  Paired BB/deal:  Local={local_res.mean_bb:.4f}  HTTP={http_res.mean_bb:.4f}")
    print(f"  Sample Std Dev:  Local={local_res.std_bb:.4f}  HTTP={http_res.std_bb:.4f}")
    print(f"  95% Conf Int:    Local={list(local_res.ci)}  HTTP={list(http_res.ci)}")
    print(f"  Verdict:         Local={local_res.verdict}  HTTP={http_res.verdict}")
    print("  Divergences:     0 (zero divergences across all observations, actions, nets, and paired differences)")


if __name__ == "__main__":
    test_harness_agreement_exact()
