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
| runtime/policy (Current: CounterplayPolicy [Counterplay_v3],             |
|                 Rollback: DrawAwarePolicy [DrawAware_v1],                |
|                           RangeAwarePolicy [RangeAware_v2],              |
|                           HeuristicPolicy [EquityBot_v1])                |
| - Fast preflop lookup (376,992 holding table in preflop.npy)             |
| - 256 joint postflop runout worlds sampled via NumPy                     |
| - Dense pair/triple card combination indexing (pair_triple.npy)          |
| - Street-separated Bayesian opponent tracking & defense adjustments      |
| - Action-conditioned range likelihood weighting                          |
| - Protected check-trapping and dynamic bet sizing                        |
| - Pot odds calculations & legal action masking fallback                  |
+--------------------------------------------------------------------------+
```

## Directory Structure

```
poker_bot/
├── agent.py               # Tournament entry point (FastAPI web server, TeamAntigravity / Counterplay_v3)
├── data/                  # Precomputed tables and frozen policy configuration
│   ├── preflop.npy        # 376,992 holding equity table (4.5 MB)
│   ├── pair_triple.npy    # Dense rank index lookup table (18.0 MB)
│   └── policy_config.json # Hyperparameter thresholds and sizing weights
├── runtime/               # Strategy execution modules
│   ├── counterplay_policy.py # Active tournament candidate (Counterplay_v3)
│   ├── dense_equity.py    # Fast vectorized Omaha equity calculation engine
│   ├── draw_aware_policy.py # Preserved rollback candidate (DrawAware_v1)
│   ├── range_aware_policy.py # Preserved rollback candidate (RangeAware_v2)
│   ├── policy.py          # Preserved baseline rollback candidate (EquityBot_v1)
│   ├── ablations.py       # Isolated ablation variants
│   ├── features.py        # Observation -> feature vectors, Monte Carlo sampling
│   └── opponent.py        # Within-half opponent tracking
├── training/              # CFR and RL training (offline)
│   ├── generic_mccfr.py   # Game-agnostic ES-MCCFR engine
│   ├── kuhn_exact.py      # Analytical ground truth & exact NashConv / Best-Response
│   ├── mccfr.py           # PLO5 MCCFR delegating to GenericMCCFRTrainer
│   └── abstraction.py     # Preflop & postflop card abstractions
├── opponents/             # Independent test opponents
│   ├── baselines.py       # Complete 12-opponent population (CallingStation, ACR, etc.)
│   ├── adversarial.py     # 9 targeted stress opponents (Threshold, StreetInversion, Trap)
│   └── serve_opponent.py  # Standalone HTTP runner for isolated match refereeing
├── evaluation/            # Benchmarking and scoring
│   ├── local_match.py     # Fast local duplicate match runner
│   ├── compare_continuation_filter.py # 1000-deal duplicate continuation filter comparison
│   ├── profile_http_runtime.py # Exact charged time-bank measurement over HTTP
│   └── summary_table.py   # Programmatic score calculation directly from verdicts
├── assets/                # Serialized models / lookup tables
├── tests/                 # Correctness & regression tests
│   ├── test_rules.py      # Rule and evaluator verification
│   ├── test_agent_protocol.py # HTTP protocol compliance
│   └── test_harness_agreement.py # Bit-for-bit local vs HTTP agreement verification
├── reports/               # Experiment logs and match results (milestone_a..e)
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
