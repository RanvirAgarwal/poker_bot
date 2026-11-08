---
name: profile-poker-runtime
description: Measure cold start, decision latency, charged bank usage, memory consumption, and stressful legal histories.
---

# Profile Poker Runtime Skill

## Purpose
Monitors computational constraints:
- Startup time within 15 seconds (including table warmup)
- Charged time bank usage strictly under 8.0s per 1000 deals (target < 5.0s)
- Request timeout compliance (< 1.0s hard limit)
- Memory consumption (< 4 GB)

## Commands
```powershell
# Measure cold start warmup latency
.\venv\Scripts\python.exe -c "import time, evaluator; t0 = time.time(); evaluator.warmup(); print('Warmup latency:', round(time.time() - t0, 4), 's')"

# Run timing test via agent protocol
.\venv\Scripts\python.exe -m pytest tests\test_agent_protocol.py -v
```

## Failure Handling
- If warmup exceeds 10s: precompute static lookup tables into binary files or serialized artifacts.
- If postflop equity estimation exceeds 5ms per decision: reduce Monte Carlo sample count or add memoization on card bitmasks.
