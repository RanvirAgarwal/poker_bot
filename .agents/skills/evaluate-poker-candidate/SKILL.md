---
name: evaluate-poker-candidate
description: Run independent opponents and duplicate matches, compute exact sample std dev and 95% CI matching the tournament judge.
---

# Evaluate Poker Candidate Skill

## Purpose
Runs full duplicate matches (two 1000-deal halves with seat swapping) to eliminate card luck and compute exact match points, paired BB per deal, and 95% confidence intervals matching `judge_engine.py`.

## Triggers
- When a new model checkpoint or policy candidate is produced
- Benchmarking candidates against the opponent registry
- Verifying regression resistance against baselines

## Commands

### Fast In-Process Benchmark Suite (Local Screening)
```powershell
cd c:\Users\ranvi\poker_bot
# Run against all 5 registered baseline opponents (100 deals duplicate)
.\venv\Scripts\python.exe evaluation\run_benchmark.py 100
```

### Full Official HTTP Duplicate Match (via judge_engine.py)
*Requires BypassSandbox: true on Windows for TCP loopback networking.*
```powershell
cd c:\Users\ranvi\poker_bot
# Test against CallingStation for 50 duplicate deals
.\venv\Scripts\python.exe evaluation\run_official_match.py 50 baseline-bots/baseline_calling_station.py

# Test against RandomBot for 50 duplicate deals
.\venv\Scripts\python.exe evaluation\run_official_match.py 50 baseline-bots/baseline_random.py
```

## Success Criteria
- Primary objective: Win or Chop (CI not strictly below 0)
- Zero rule violations or protocol errors (`errors == 0`)
- Charged thinking time bank consumption under 5.0 seconds per half
