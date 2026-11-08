# TAMU Datathon Poker Bot: Project Memory

## 1. Objective and Verified Constraints
- **Game Variant**: Heads-up Short Deck 5-Card Pot-Limit Omaha (PLO5)
- **Deck**: 36 cards (6, 7, 8, 9, T, J, Q, K, A in 4 suits)
- **Hand Ranking**: Flush > Full House; Three of a Kind > Straight; Wheel is A-6-7-8-9 (lowest straight)
- **Omaha Selection**: Exactly 2 hole cards + 3 board cards (5-card lookup table pre-scored)
- **Stacks & Blinds**: 80 starting chips (reset each hand); 1 SB, 2 BB; 4 voluntary raises cap per street
- **Match Structure**: 1,000 duplicate deals in 2 fresh-server halves (2,000 hands total); seats swap in half 2
- **Hardware & Environment**: 1 CPU, 4 GB RAM, no runtime internet, read-only filesystem except `/tmp`
- **Time Limits**: 8.0s charged time bank per half; 1ms network grace per request; 1.0s hard request timeout; 15s startup
- **Forfeit Rules**: 5 errors in either half forfeits the match
- **Scoring**: Paired BB/deal mean across halves; sample std dev (ddof=1); 95% CI (z=1.96). CI strictly above 0 = WIN (1 pt), strictly below 0 = LOSS (0 pts), includes 0 = CHOP (0.5 pts)

## 2. Current Status
- **Independently Verified & Tested**:
  - **Leading Candidate**: `RangeAware_v2` (`agent.py` at root, core logic in `runtime/range_aware_policy.py`, with continuation filtering enabled).
  - **Rollback Baseline**: `EquityBot_v1` (frozen in `runtime/policy.py`).
  - **Official Protocol & Tests**: 43 unit, official, and agreement tests in `tests/` pass cleanly -> **43/43 PASSED**.
  - **Strengthened Harness Agreement**: Bit-for-bit audit in `tests/test_harness_agreement.py` comparing observations (`hole_cards`, `board`, `button_seat`), complete action sequences `(street, action, amount)`, hand net payoffs, paired differences vector, sample std dev ($ddof=1$), 95% CI, and tournament verdict between local runner and official HTTP judge engine -> **0 divergences across all dimensions**.
  - **Controlled Continuation Filter Study (66 Matches, 132,000 Hands Total)**:
    - 1,000-deal duplicate matches with matched seeds comparing `WithFilter` vs `NoFilter`:
    - `RangeAware_v2_WithFilter`: **31.0 / 33.0 points (93.9% point fraction)**, 29 Wins, 4 Chops, 0 Losses, across-match std dev $\pm 2.82$ BB/deal.
    - `RangeAware_v2_NoFilter`: **30.5 / 33.0 points (92.4% point fraction)**, 28 Wins, 5 Chops, 0 Losses, across-match std dev $\pm 2.99$ BB/deal.
    - Strong opponents: `WithFilter` beat `NoFilter` by **+0.421 BB/deal** vs `size_aware_equity`, **+0.179 BB/deal** vs `action_conditioned_range`, and **+0.114 BB/deal** vs `trained_response_bot`.
    - Payoff: +280,751 chips (`WithFilter`) vs +282,052 chips (`NoFilter`) — 0.46% difference, well within sampling error ($\pm 0.02$ BB/deal).
    - Decision: `RangeAware_v2_WithFilter` selected as the active frozen submission.
  - **Multi-Seed 1,000-Deal Empirical Benchmark (120,000 hands total across both candidates, 60,000 per candidate)**:
    - 60 complete duplicate matches across 5 independent seeds x 1,000 deals on 6 critical opponents:
    - `RangeAware_v2`: **30 Wins, 0 Chops, 0 Losses (30.0 / 30.0 points = 100.0% Win Rate)**!
    - `EquityBot_v1`: **19 Wins, 11 Chops, 0 Losses (24.5 / 30.0 points = 81.7% match-point fraction; 63.3% win fraction)**.
    - Vs `action_conditioned_range`: `RangeAware_v2` scored **+1.93 BB/deal (5W-0C-0L)** vs EquityBot's +0.34 BB/deal (0W-5C-0L) — a gain of **+1.59 BB/deal**.
    - Vs `size_aware_equity`: `RangeAware_v2` scored **+1.42 BB/deal (5W-0C-0L)** vs EquityBot's +0.07 BB/deal (0W-5C-0L) — a gain of **+1.34 BB/deal**.
    - Vs `calling_station`: `RangeAware_v2` scored **+12.13 BB/deal** vs EquityBot's +11.70 BB/deal — zero regression on soft targets.
  - **Targeted Adversarial Stress Suite (9 Opponents)**:
    - `RangeAware_v2` scored **8 Wins, 1 Chop, 0 Losses (8.5 / 9.0 points = 94.4%)**.
    - Street-separated aggression tracking neutralized `StreetInversionAttacker` (+7.11 BB/deal vs EquityBot's +5.42 BB/deal).
    - Protected checking (trapping with strong hands OOP 20% on flop/turn) beat `CheckTrapAttacker` (+4.57 BB/deal).
  - **Official Full-Length HTTP Tournament Matches (2,000 hands each with fresh server restart between halves)**:
    - Vs `action_conditioned_range`: **+2.164 BB/deal**, 95% CI **[+1.516, +2.812] BB/deal** -> **AGENT1_WIN** (3.40s / 5.08s of 8.0s time bank, 0 errors across 6,604 calls).
    - Vs `always_raise`: **+2.750 BB/deal**, 95% CI **[+1.230, +4.270] BB/deal** -> **AGENT1_WIN** (0.82s / 0.70s bank, 0 errors across 6,233 calls).
    - Vs `size_aware_equity`: **+0.818 BB/deal**, 95% CI **[-0.026, +1.662] BB/deal** -> **CHOP** (3.75s / 4.31s bank, 0 errors across 6,908 calls).
  - **CFR Engine Unification & Exact Best-Response Audit**:
    - `training/mccfr.py` wraps `Game` into `PLO5ExtensiveGame` and calls `GenericMCCFRTrainer` directly, proving PLO5 training executes the exact same update algorithm audited on Kuhn.
    - Verified Kuhn best-response calculation evaluates pure strategy vectors over observable player information sets ($64$ pure strategies per seat across $6$ observable infosets) with zero access to the opponent's private cards.
  - **Exact Runtime & Time Bank Profile (Host Measurements)**:
    - Cold start: **1.037s / 15.0s budget** over HTTP.
    - Complete HTTP Requests (1,000 deals): 1,931 requests; Wall-clock total: 2.119s.
    - Exact charged time bank ($\sum \max(0, t_{\text{req}} - 0.001)$): **0.690s / 8.000s bank** (PASS, **91.4% margin remaining**).
    - Decision latency: Mean **1.10 ms**, Median **0.92 ms**, P95 **2.48 ms**, P99 **3.25 ms**, Max **18.08 ms / 1,000.0 ms hard limit**.
    - Deep legal history (32 actions up to raise cap over HTTP): Mean **2.00 ms**, Max **2.92 ms**.
    - Reliability: **0 errors across > 30,000 HTTP requests**.
  - **Review Bundle Exported**:
    - Packaged at `release/review_bundle_RangeAware_v2.zip` containing all source, opponent suites, evaluation code, tests, manifests, and raw JSON verdicts.
- **Implemented but Unverified / Outstanding**:
  - Container build via `tools/check_build.sh`: Docker CLI 29.2.1 is installed on host, but the Docker Desktop daemon service is offline (`pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`). Starting Docker Desktop on Windows requires host user action to launch the application. Containerized build execution remains **outstanding**. All existing timing/memory profiling metrics are accurately documented as **Host Measurements**.
- **Blocked**: None.

## 3. Architecture Map
- `agent.py`: Submission entry point at project root (`TeamAntigravity / RangeAware_v2`).
- `runtime/`:
  - `range_aware_policy.py`: `RangeAwarePolicy` (`RangeAware_v2`), featuring street-separated Bayesian aggression tracking, likelihood-weighted range conditioning, protected checking, mixed sizing, and continuation equity modeling.
  - `policy.py`: `HeuristicPolicy` (`EquityBot_v1` - frozen immediate rollback).
  - `ablations.py`: Isolated ablation policies (`EquityOnly`, `RangeOnly`, `RangeAndAdapt`, `Complete_v2`).
  - `features.py`: `omaha_best_score`, `hand_strength_sampled`, preflop hand quality heuristics.
  - `cfr_policy.py`: `CFRPolicy` querying average strategy tables from trained blueprints.
  - `opponent.py`: Within-half memory tracking.
- `training/`:
  - `generic_mccfr.py`: Game-agnostic ES-MCCFR engine implementing `ExtensiveGame` protocol.
  - `kuhn_exact.py`: Kuhn game adapter and exact backward-induction Best-Response / NashConv calculator.
  - `abstraction.py`: Card bucketing (10 preflop, 10 postflop) and infoset key hashing.
  - `mccfr.py`: PLO5 external-sampling MCCFR trainer delegating to `GenericMCCFRTrainer`.
  - `train.py`: CLI driver for offline CFR training.
  - `audit_coverage.py`: Audits hit rate and fallback distribution on held-out deals.
- `opponents/`:
  - `baselines.py`: Complete 12-opponent population (CheckFold, CallingStation, Random, AlwaysRaise, GuideCheapCall, EquityCall, SizeAwareEquity, ActionConditionedRange, AdaptiveExploiter, TellExploiter, CheckAttacker, FrozenEquityBotAttacker).
  - `adversarial.py`: 9 targeted stress-test opponents (`ThresholdAttackerBelow`, `ThresholdAttackerAbove`, `StreetInversionAttacker`, `RiverBluffAttacker`, `ChameleonAttacker`, `FoldBullyAttacker`, `CheckTrapAttacker`, `SizingTellDisguiser`, `TrainedResponseBot`).
  - `serve_opponent.py`: Standalone HTTP server for isolated match testing of any registered opponent.
- `evaluation/`:
  - `local_match.py`: In-process duplicate simulator replicating exact judge scoring.
  - `summary_table.py`: Programmatic score calculator and Markdown table generator.
  - `diagnose_losses.py`: Hand-by-hand diagnostic tracing of chip loss contexts.
  - `benchmark_candidates.py`: Side-by-side comparative benchmarking against 12-opponent suite with raw JSON export.
  - `run_critical_multiseed_evaluation.py`: 5-seed 1,000-deal duplicate runner across critical opponents.
  - `run_full_tournament_match.py`: Multi-process HTTP runner with fresh process restart per half.
  - `run_adversarial_and_ablations.py`: Runs adversarial suite and 4-variant ablation matrix.
  - `profile_runtime.py`: Measures cold start, memory, request latency percentiles, and deep history stress tests.
  - `profile_http_runtime.py`: Measures exact charged time bank (`sum(max(0, req - 0.001))`) over complete HTTP requests.
  - `compare_continuation_filter.py`: 1,000-deal duplicate comparison runner between continuation filter variants.
- `release/`:
  - `review_bundle_RangeAware_v2.zip`: Reviewable release package (145 files, 0.30 MB).
- `reports/`:
  - `milestone_a_report.md`: Initial architecture and screening benchmark.
  - `milestone_b_report.md`: Full-length tournament validation, CFR audit, and opponent population.
  - `milestone_c_report.md`: Range-aware candidate, multi-seed evaluation, and complete CFR audit.
  - `milestone_d_report.md`: Adversarial validation, component ablations, runtime profiling, and reviewable release.
  - `milestone_e_report.md`: Candidate selection, harness agreement evidence, and release verification.
  - `raw_matches/`: Complete raw judge JSON files (including `continuation_filter_study.json`).

## 4. Decisions Log
- **DEC-001**: Clean separation of FastAPI plumbing from strategy code in `runtime/`.
- **DEC-002**: Monte Carlo hand strength sampling (80-100 samples) rather than full enumeration (~0.5ms vs 50ms).
- **DEC-003**: In-process local match runner replicating judge_engine scoring for rapid iteration.
- **DEC-004**: Strict isolation of all within-half learning in `memory` dict (no global leaks).
- **DEC-005**: Generalized `omaha_best_score` to evaluate exactly 2 hole + 3 board cards for flop, turn, and river.
- **DEC-006**: Stage official tournament referee files at project root to ensure `test_agent.py` and Docker build context match submission.
- **DEC-007**: Retain `EquityBot_v1` as baseline rollback candidate based on empirical benchmark evidence.
- **DEC-008**: Build `RangeAware_v2` with street-separated Bayesian opponent aggression estimation ($\hat{r}_{\text{pf}} = (R_{\text{pf}}+2.5)/(N_{\text{pf}}+10)$, $\hat{r}_{\text{post}} = (R_{\text{post}}+1.5)/(N_{\text{post}}+10)$) to prevent preflop aggression from distorting river evaluations.
- **DEC-009**: Isolate continuation range equity from current range equity to prevent value-betting into hands that only call when ahead.
- **DEC-010**: Promote `RangeAware_v2` to active tournament entry point (`agent.py`). Keep `EquityBot_v1` frozen in `runtime/policy.py` as immediate verified rollback.
- **DEC-011**: Add protected checking (trapping with strong hands OOP 20% on flop/turn) and mixed bet sizing (65% pot / 35% half-pot on strong hands) to eliminate capped checking ranges and deterministic sizing tells.
- **DEC-012**: Unify `training/mccfr.py` with `GenericMCCFRTrainer` so PLO5 training executes the exact same engine validated against analytical Kuhn ground truth.
- **DEC-013**: Retain continuation filtering in `RangeAware_v2` based on the controlled 66-match 1,000-deal duplicate study (31.0/33 vs 30.5/33 match points, lower across-match variance, +0.42 BB/deal vs size_aware_equity).

## 5. Skills Catalog
- `.agents/skills/verify-poker-rules/SKILL.md`: Validates ranking, 2+3 selection, raise caps, and rules (Usable).
- `.agents/skills/evaluate-poker-candidate/SKILL.md`: Runs local benchmark suite and official HTTP matches (Usable).
- `.agents/skills/profile-poker-runtime/SKILL.md`: Measures cold start, decision latency, and time bank consumption (Usable).
- `.agents/skills/run-poker-training/SKILL.md`: Offline CFR/response training pipeline (Usable).
- `.agents/skills/export-poker-release/SKILL.md`: Packaging, smoke tests, and Docker verification (Usable).
- `.agents/skills/maintain-project-memory/SKILL.md`: Reconciles persistent project state in MEMORY.md (Usable).

## 6. Best Working Candidate
- **Identifier**: `RangeAware_v2` (with continuation filtering)
- **Entry Point**: `agent.py` at root
- **Participant Name**: `TeamAntigravity`
- **Agent Name**: `RangeAware_v2`
- **Core Modules**: `runtime/features.py`, `runtime/range_aware_policy.py`, `runtime/opponent.py`
- **Rollback Version**: `EquityBot_v1` (`runtime/policy.py`)
- **Measured Evidence**:
  - Controlled continuation filter study (66 matches x 1,000 duplicate deals, 132,000 hands total): **31.0 / 33.0 points (93.9% point fraction)** with 29 wins, 4 chops, 0 losses.
  - Multi-seed benchmark (5 seeds x 1,000 deals, 120,000 hands total across both candidates): **30.0 / 30.0 points (100.0% win rate)** vs EquityBot's 24.5/30 (81.7% match points, 63.3% win rate).
  - Adversarial stress suite (9 opponents): **8.5 / 9.0 points (94.4%)** with 8 wins, 1 chop, 0 losses.
  - Official HTTP 1,000-deal tournament match: **+2.164 BB/deal** (95% CI [+1.516, +2.812]) vs `action_conditioned_range` (`AGENT1_WIN`).
  - Official HTTP 1,000-deal tournament match: **+2.750 BB/deal** (95% CI [+1.230, +4.270]) vs `always_raise` (`AGENT1_WIN`).
  - Suite screening: **9.0 - 9.5 / 12.0 points** with 0 losses.
  - Exact Runtime (Host measurements): Cold start 1.04s; decision mean 1.10ms, P95 2.48ms, P99 3.25ms; exact charged bank 0.690s / 8.000s per 1,000-deal half; 0 errors across > 30,000 HTTP requests.

## 7. Resume Instructions
- Run full test suite: `.\venv\Scripts\python.exe -m pytest tests -v`
- Run harness agreement audit: `.\venv\Scripts\python.exe tests\test_harness_agreement.py`
- Run continuation filter study: `.\venv\Scripts\python.exe evaluation\compare_continuation_filter.py`
- Run exact HTTP runtime profiler: `.\venv\Scripts\python.exe evaluation\profile_http_runtime.py`
- Re-export review bundle: `.\venv\Scripts\python.exe tools\export_review_bundle.py`
- Run official full-length HTTP match: `.\venv\Scripts\python.exe evaluation\run_full_tournament_match.py --agent1 agent.py --agent2 opponents\serve_opponent.py --opp-bot action_conditioned_range --deals 1000 --seed test_seed`
