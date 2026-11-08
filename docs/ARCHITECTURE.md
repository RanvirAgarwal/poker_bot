# Architecture: Heads-Up Short Deck PLO5 Poker Bot

## System Overview

```
                          TOURNAMENT JUDGE (judge_engine.py)
                                     |
                                  HTTP/JSON
                                     |
                                     v
+--------------------------------------------------------------------------+
| agent.py (FastAPI Server, Port 5008)                                     |
|                                                                          |
|  Endpoints:                                                              |
|    GET  /           -> Health check + Agent ID                           |
|    POST /new-half   -> Reset memory, apply config                        |
|    POST /act        -> Receive obs + batch hand_results -> choose_action |
|    POST /hand-end   -> Receive final hand_results                        |
+--------------------------------------------------------------------------+
       |                                   |
       v                                   v
+--------------------+            +--------------------+
| runtime/features   |            | runtime/opponent   |
| - Hand strength    |            | - Opponent model   |
| - Preflop quality  |            | - Hand history     |
| - Position/Pot     |            | - Showdown stats   |
+--------------------+            +--------------------+
       \                                   /
        \                                 /
         v                               v
+--------------------------------------------------------------------------+
| runtime/policy (Current: HeuristicPolicy, Planned: CFR-trained)          |
| - Equity-based decisions                                                 |
| - Pot odds calculations                                                  |
| - Mixed strategy sampling                                                |
| - Legal action masking & fallback                                        |
+--------------------------------------------------------------------------+
```

## Directory Structure

```
poker_bot/
├── agent.py               # Tournament entry point (FastAPI web server)
├── runtime/               # Strategy execution modules
│   ├── features.py        # Observation -> feature vectors
│   ├── policy.py          # Strategy implementations
│   └── opponent.py        # Within-half opponent tracking
├── training/              # CFR and RL training (offline)
├── opponents/             # Independent test opponents
│   └── baselines.py       # CheckFold, CallingStation, Random, EquityCall
├── evaluation/            # Benchmarking and scoring
│   └── local_match.py     # Fast local duplicate match runner
├── assets/                # Serialized models / lookup tables
├── tests/                 # Correctness & regression tests
│   ├── test_rules.py      # Rule and evaluator verification
│   └── test_agent_protocol.py  # HTTP protocol compliance
├── reports/               # Experiment logs and match results
├── docs/                  # Architecture & decisions
│   ├── ARCHITECTURE.md    # This file
│   └── DECISIONS.md       # Decision log
└── starter/               # Official starter (read-only reference)
```

## Design Constraints & Compliance

| Constraint | Limit | Implementation |
|------------|-------|----------------|
| Startup time | 15s | `warmup()` runs at import; pre-computed tables |
| Thinking time bank | 8.0s / half | Fast feature extraction (~100 MC samples); <5ms/call |
| Per-request timeout | 1.0s | Hard deadline via socket reader |
| Grace period | 1ms | Excluded from charged time |
| Memory limit | 4 GB | Lightweight representations; compact lookups |
| CPU limit | 1 core | Single-threaded; no multi-process at runtime |
| Runtime network | None | All assets bundled locally |
| Error limit | 5 / half | Multi-tier fallback: heuristic -> check/fold |
| Memory reset | Per half | Strict half isolation; no cross-half state |

## Module Responsibilities

1. **`agent.py`**: Web server layer. Never implements strategy logic directly. Translates HTTP requests to typed dataclasses, invokes `runtime/`, catches all exceptions, returns safe actions.
2. **`runtime/features.py`**: Pure functions converting `Observation` to numeric features. Monte Carlo hand strength sampling against random opponent holdings.
3. **`runtime/policy.py`**: Decision-making engine. Must return an `Action` in `obs.legal_actions`. Handles pot odds, SPR, position, and hand strength.
4. **`runtime/opponent.py`**: Per-half opponent modeling. Stored exclusively in the judge-managed `memory` dict.
5. **`evaluation/local_match.py`**: Runs duplicate matches in-process without HTTP overhead. Replicates `judge_engine.py` scoring exactly (paired BB, sample standard deviation, 95% CI).
