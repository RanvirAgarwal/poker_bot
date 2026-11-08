"""
evaluation/run_full_tournament_match.py - Execute full-length tournament match with process isolation.

Restarts fresh server processes for both agents between Half 1 and Half 2,
matching the tournament's pod lifecycle exactly. Saves raw judge JSONs.
"""

from __future__ import annotations

import sys
import os
import subprocess
import time
import json
import argparse
from typing import Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from judge_engine import combine_halves, HalfResult, MatchResult, format_report


def run_half_process(
    agent1_target: str,
    agent2_script: str,
    half: int,
    deals: int,
    seed: str,
    output_json: str,
    port1: int = 5008,
    port2: int = 5009,
    opp_bot: str = "calling_station",
    use_container: bool = False,
) -> Dict[str, Any]:
    python_exe = sys.executable

    env1 = os.environ.copy()
    env1["PORT"] = str(port1)
    env2 = os.environ.copy()
    env2["PORT"] = str(port2)
    env2["OPPONENT_BOT"] = opp_bot

    container_name = f"poker-agent1-h{half}-{int(time.time())}"
    p1 = None

    if use_container:
        print(f"\n[Half {half}] Spawning restricted Docker container ({agent1_target}) on port {port1}...")
        # Enforce exact tournament container constraints: 1 CPU, 4 GB RAM, read-only FS, 512m tmpfs
        docker_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port1}:{port1}",
            "--read-only",
            "--tmpfs", "/tmp:rw,nosuid,nodev,size=512m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "256",
            "--cpus", "1",
            "--memory", "4g",
            "-e", f"PORT={port1}",
            agent1_target,
        ]
        res_d = subprocess.run(docker_cmd, capture_output=True, text=True)
        if res_d.returncode != 0:
            raise RuntimeError(f"Failed to start container {agent1_target}: {res_d.stderr}")
    else:
        print(f"\n[Half {half}] Spawning fresh server process ({agent1_target})...")
        agent1_dir = os.path.dirname(os.path.abspath(agent1_target)) if os.path.isfile(agent1_target) else ROOT_DIR
        p1 = subprocess.Popen([python_exe, agent1_target], env=env1, cwd=agent1_dir)

    print(f"[Half {half}] Spawning opponent server process ({agent2_script}, bot={opp_bot})...")
    agent2_dir = os.path.dirname(os.path.abspath(agent2_script)) if os.path.isfile(agent2_script) else ROOT_DIR
    p2 = subprocess.Popen([python_exe, agent2_script], env=env2, cwd=agent2_dir)

    try:
        # Give servers a moment to bind and warmup
        time.sleep(2.0)

        cmd = [
            python_exe,
            os.path.join(ROOT_DIR, "judge_engine.py"),
            f"--agent1=http://127.0.0.1:{port1}",
            f"--agent2=http://127.0.0.1:{port2}",
            f"--half={half}",
            f"--deals={deals}",
            f"--seed={seed}",
            f"--json={output_json}",
        ]
        print(f"[Half {half}] Executing judge_engine command: {' '.join(cmd)}")
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(res.stdout)
        if res.stderr:
            print("[STDERR]", res.stderr)

        if not os.path.exists(output_json):
            raise RuntimeError(f"Half {half} did not produce JSON output at {output_json}")

        agent1_info = {}
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{port1}/", timeout=1.0) as req:
                agent1_info = json.loads(req.read().decode("utf-8"))
        except Exception as e:
            agent1_info = {"query_error": str(e)}

        with open(output_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        if agent1_info:
            data["agent1_info"] = agent1_info
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        return data

    finally:
        print(f"[Half {half}] Terminating processes / containers...")
        if use_container:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        elif p1:
            try:
                p1.terminate()
                p1.wait(timeout=2)
            except Exception:
                try:
                    p1.kill()
                except Exception:
                    pass
        if p2:
            try:
                p2.terminate()
                p2.wait(timeout=2)
            except Exception:
                try:
                    p2.kill()
                except Exception:
                    pass
        time.sleep(0.5)


def run_full_duplicate_match(
    agent1_script: str,
    agent2_script: str,
    deals: int = 1000,
    seed: str = "tournament_seed_1",
    output_dir: str = "reports/raw_matches",
    opp_bot: str = "calling_station",
    use_container: bool = False,
    match_id: Optional[str] = None,
) -> MatchResult:
    if match_id is None:
        match_id = seed
    os.makedirs(output_dir, exist_ok=True)
    h1_json = os.path.join(output_dir, f"{match_id}_half1.json")
    h2_json = os.path.join(output_dir, f"{match_id}_half2.json")
    match_json = os.path.join(output_dir, f"{match_id}_match.json")

    print("=" * 75)
    print(f"OFFICIAL TOURNAMENT MATCH: {deals} deals duplicate (2,000 hands total)")
    print(f"Agent 1: {agent1_script} (Container: {use_container})")
    print(f"Agent 2: {agent2_script} (bot: {opp_bot})")
    print(f"Seed: {seed}")
    print("=" * 75)

    data1 = run_half_process(agent1_script, agent2_script, 1, deals, seed, h1_json, opp_bot=opp_bot, use_container=use_container)
    data2 = run_half_process(agent1_script, agent2_script, 2, deals, seed, h2_json, opp_bot=opp_bot, use_container=use_container)

    half1 = HalfResult.from_dict(data1)
    half2 = HalfResult.from_dict(data2)

    match_result = combine_halves(half1, half2)
    with open(match_json, "w", encoding="utf-8") as f:
        f.write(match_result.to_json(indent=2))

    print("\n" + "=" * 75)
    print("OFFICIAL COMBINED MATCH RESULT")
    print("=" * 75)
    print(format_report(match_result))
    print(f"\nSaved raw JSON report: {match_json}")
    return match_result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent1", default="agent.py")
    parser.add_argument("--agent2", default="starter/baseline-bots/baseline_calling_station.py")
    parser.add_argument("--deals", type=int, default=1000)
    parser.add_argument("--seed", default="seed_1")
    parser.add_argument("--outdir", default="reports/raw_matches")
    parser.add_argument("--opp-bot", default="calling_station")
    parser.add_argument("--match-id", default=None, help="Identifier prefix for saved match JSON files")
    parser.add_argument("--container", action="store_true", help="Run agent1 inside restricted Docker container")
    parser.add_argument("--container-image", default="poker-agent-check:latest")
    args = parser.parse_args()

    a1 = args.container_image if args.container else os.path.abspath(args.agent1)
    a2 = os.path.abspath(args.agent2)
    run_full_duplicate_match(
        a1, a2,
        deals=args.deals,
        seed=args.seed,
        output_dir=args.outdir,
        opp_bot=args.opp_bot,
        use_container=args.container,
        match_id=args.match_id,
    )

