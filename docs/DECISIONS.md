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

## DEC-005: Generalized Omaha Scoring
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Evaluating flop and turn boards requires subset combinations of board cards.
- **Decision**: Implement `omaha_best_score` to evaluate exactly 2 hole + 3 board cards for flop (3 board cards), turn (4 choose 3), and river (5 choose 3).
- **Rationale**: Fast, bug-free valuation across all game streets using the official 5-card lookup table.

## DEC-006: Staging Official Referee Files at Project Root
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: The official test runner `test_agent.py` and Docker build context require agent.py and dependencies to reside at the project root.
- **Decision**: Stage referee files (`game.py`, `evaluator.py`, `judge_engine.py`, `agent.py`) at root while maintaining `starter/` as clean read-only reference.
- **Rationale**: Eliminates path discrepancies and guarantees identical test execution between local development and tournament submission.

## DEC-007: Retain EquityBot_v1 as Immutable Rollback Candidate
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Developing new policies requires an immutable benchmark and rollback safety net.
- **Decision**: Freeze `EquityBot_v1` in `runtime/policy.py`.
- **Rationale**: Protects against regressions while exploring aggressive opponent modeling.

## DEC-008: Street-Separated Bayesian Aggression Tracking
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Single global aggression metrics allow loose preflop play to incorrectly distort river hand evaluations.
- **Decision**: Implement independent preflop ($\hat{r}_{\text{pf}}$) and postflop ($\hat{r}_{\text{post}}$) raise tracking with Beta priors.
- **Rationale**: Prevents preflop bluffers who become value-heavy on later streets from being misclassified as river maniacs.

## DEC-009: Separation of Continuation Range Equity from Current Range Equity
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Opponents fold their weakest hands when facing bets, resulting in a stronger continuation range.
- **Decision**: Compute both current equity and continuation equity, requiring both thresholds to be satisfied before betting or raising.
- **Rationale**: Prevents value-betting into hands that only call when ahead.

## DEC-010: Promote RangeAware_v2 as Active Candidate
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Comprehensive 5-seed 1,000-deal duplicate benchmarks proved `RangeAware_v2` achieved a 100% win rate (30.0/30.0 points) vs `EquityBot_v1`'s 81.7% match points.
- **Decision**: Point `_POLICY` in `agent.py` to `RangeAwarePolicy`.
- **Rationale**: Massive empirical superiority (+1.59 BB/deal vs action-conditioned opponent, +1.34 BB/deal vs size-aware opponent) with zero regression on soft targets.

## DEC-011: Protected Check-Trapping and Mixed Bet Sizing
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Check-folding weak hands and always betting strong hands creates capped checking ranges and predictable sizing tells.
- **Decision**: Trap-check 20% of monster hands OOP on flop/turn and mix value bet sizes (65% pot, 35% half-pot).
- **Rationale**: Eliminates exploitation by aggressive check-attackers and disguises nut holdings.

## DEC-012: Unification of PLO5 and Generic MCCFR Engine
- **Date**: 2026-11-07
- **Status**: Accepted
- **Context**: Proving CFR correctness requires mathematical audit against analytical ground truth.
- **Decision**: Adapt `training/mccfr.py` to delegate to `GenericMCCFRTrainer` and validate on analytical Kuhn poker ground truth.
- **Rationale**: Guarantees that PLO5 CFR updates execute the exact regret-matching and average strategy algorithms proven to converge to Nash equilibrium.

## DEC-013: Retain Continuation Filtering in RangeAware_v2
- **Date**: 2026-11-08
- **Status**: Accepted
- **Context**: Initial 100-deal ablation suggested a minor chip payoff difference between with-filter and no-filter variants.
- **Decision**: Conduct an exhaustive 66-match (132,000 hand) duplicate study and retain continuation filtering (`RangeAware_v2_WithFilter`).
- **Rationale**: `WithFilter` achieved higher tournament points (31.0/33 vs 30.5/33), reduced across-match variance ($\pm 2.82$ vs $\pm 2.99$ BB/deal), and produced decisive gains against strong opponents (+0.421 BB/deal vs size_aware_equity).
