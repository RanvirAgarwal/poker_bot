"""
evaluation/run_official_match.py - Orchestrate official HTTP duplicate match via judge_engine.

Spawns agent1 (our bot) and agent2 (opponent) as uvicorn server processes,
executes judge_engine against them over HTTP, records timing/bank/stats,
and shuts down the servers cleanly.
"""

from __future__ import annotations

import sys
import os
import subprocess
import time
import json
import signal

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STARTER_DIR = os.path.join(ROOT_DIR, "starter")
sys.path.insert(0, STARTER_DIR)
sys.path.insert(0, ROOT_DIR)

from judge_engine import main_play


def run_http_match(agent2_script: str = "baseline-bots/baseline_random.py",
                   deals: int = 50, seed: str = "http_test_1"):
    python_exe = sys.executable

    # Ports
    port1 = 5008
    port2 = 5009

    env1 = os.environ.copy()
    env1["PORT"] = str(port1)
    env2 = os.environ.copy()
    env2["PORT"] = str(port2)

    print(f"Starting Agent 1 (root agent.py) on port {port1}...")
    p1 = subprocess.Popen(
        [python_exe, os.path.join(ROOT_DIR, "agent.py")],
        env=env1,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    opp_path = os.path.join(STARTER_DIR, agent2_script) if not os.path.isabs(agent2_script) else agent2_script
    print(f"Starting Agent 2 ({agent2_script}) on port {port2}...")
    p2 = subprocess.Popen(
        [python_exe, opp_path],
        env=env2,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait a moment for servers to start
        time.sleep(2.0)

        # Run judge_engine
        print(f"\nRunning judge_engine: deals={deals}, seed={seed}...")
        argv = [
            f"--agent1=http://127.0.0.1:{port1}",
            f"--agent2=http://127.0.0.1:{port2}",
            f"--deals={deals}",
            f"--seed={seed}",
        ]
        ret = main_play(argv)
        return ret
    finally:
        print("\nShutting down server processes...")
        for p in (p1, p2):
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    deals = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    opp = sys.argv[2] if len(sys.argv) > 2 else "baseline-bots/baseline_random.py"
    run_http_match(agent2_script=opp, deals=deals)
