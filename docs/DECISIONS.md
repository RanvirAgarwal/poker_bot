# Consequential Decisions Log

## DEC-001: Separation of Server Plumbing and Strategy Logic
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: The official `agent.py` combines FastAPI plumbing with strategy code.
- **Decision**: Keep `agent.py` as a thin wrapper and move all strategy, feature extraction, and opponent modeling to `runtime/`.
- **Rationale**: Enables unit testing of strategy components without running an HTTP server, allows fast local match simulation, and cleanly separates tournament interface from algorithmic improvements.
- **Tradeoffs**: Requires maintaining the import path cleanly. Negligible overhead.

## DEC-002: Monte Carlo Hand Strength over Full Enumeration
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Full hand strength calculation postflop requires enumerating C(26, 5) = 65,780 opponent hands, which takes ~50-100ms in pure Python.
- **Decision**: Use sampled Monte Carlo estimation with 80-150 random opponent hands for postflop decisions.
- **Rationale**: With 8-second time bank across 1000 hands (~1500 decisions), we have an average of ~5ms per decision. Full enumeration would exhaust the time bank in ~100 hands.
- **Tradeoffs**: Approximate equity vs exact equity; random variance in estimates. Mitigated by using fixed seed per policy instance and sampling sufficient hands.

## DEC-003: In-Process Local Match Evaluation
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Running full matches via `judge_engine.py` requires three separate processes (two bot servers + judge) and HTTP overhead (~100-200ms per hand).
- **Decision**: Implement `evaluation/local_match.py` that directly calls agent functions in-process, while exactly replicating the duplicate scoring, paired BB calculation, and 95% confidence intervals from `judge_engine.py`.
- **Rationale**: Enables evaluating 200-deal matches in seconds rather than minutes, dramatically speeding up the experimental loop.
- **Tradeoffs**: Does not test the HTTP networking layer. Mitigated by running smoke tests and occasional full HTTP matches with `judge_engine.py`.

## DEC-004: Strict Memory Dict Isolation
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: In the tournament, each half runs in a fresh Kubernetes pod. Locally, both halves can run in the same process where global variables persist.
- **Decision**: Store all learning and opponent state strictly in the `memory` dict passed to callbacks, never in module-level global variables.
- **Rationale**: Guarantees identical behavior between local testing and tournament deployment; avoids accidentally relying on state leaks.
