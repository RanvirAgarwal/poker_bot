---
name: run-poker-training
description: Launch and monitor CFR or response training, log configurations, seeds, throughput, and checkpoint representations.
---

# Run Poker Training Skill

## Purpose
Executes offline Counterfactual Regret Minimization (CFR) or opponent exploitation training to generate blueprint policies and response tables.

## Status: Milestone B/C Planned
Currently the baseline heuristic policy (`HeuristicPolicy` in `runtime/policy.py`) serves as the working tournament candidate. Training scripts will reside in `training/`.

## Planned Commands
```powershell
# Launch CFR training run (future)
.\venv\Scripts\python.exe training\train_cfr.py --iterations 50000 --save-interval 10000 --checkpoint assets/cfr_v1.pkl
```

## Checkpoint Protocol
- Checkpoints saved under `assets/`
- Every run logs git commit, seed, iteration count, exploitability against baseline benchmarks

