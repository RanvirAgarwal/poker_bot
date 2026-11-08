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
  - **Promoted Candidate**: `RangeAware_v2` (`agent.py` at root, implementation in `runtime/range_aware_policy.py`).
  - **Official Protocol & Tests**: 40 unit and official tests in `tests/` pass cleanly -> **40/40 PASSED** (includes official test suite exercising root `agent.py`).
  - **Multi-Seed 1,000-Deal Empirical Benchmark (60,000 hands total)**:
    - Evaluated across 5 independent seeds x 1,000 duplicate deals against 6 critical opponents (`action_conditioned_range`, `size_aware_equity`, `always_raise`, `adaptive_exploiter`, `frozen_equity_attacker`, `calling_station`):
    - `RangeAware_v2`: **30 Wins, 0 Chops, 0 Losses (30.0 / 30.0 points = 100.0% Win Rate)**!
    - `EquityBot_v1`: **19 Wins, 11 Chops, 0 Losses (24.5 / 30.0 points = 81.7% Win Rate)**.
    - Vs `action_conditioned_range`: `RangeAware_v2` scored **+1.93 BB/deal (5W-0C-0L)** vs EquityBot's +0.34 BB/deal (0W-5C-0L) — a gain of **+1.59 BB/deal**.
    - Vs `size_aware_equity`: `RangeAware_v2` scored **+1.42 BB/deal (5W-0C-0L)** vs EquityBot's +0.07 BB/deal (0W-5C-0L) — a gain of **+1.34 BB/deal**.
    - Vs `calling_station`: `RangeAware_v2` scored **+12.13 BB/deal** vs EquityBot's +11.70 BB/deal — zero regression on soft targets.
  - **Official Full-Length HTTP Tournament Matches (2,000 hands each with fresh server restart between halves)**:
    - Vs `action_conditioned_range`: **+2.164 BB/deal**, 95% CI **[+1.516, +2.812] BB/deal** -> **AGENT1_WIN** (3.40s / 5.08s of 8.0s time bank, 0 errors across 6,604 calls).
    - Vs `always_raise`: **+2.750 BB/deal**, 95% CI **[+1.230, +4.270] BB/deal** -> **AGENT1_WIN** (0.82s / 0.70s bank, 0 errors across 6,233 calls).
    - Vs `size_aware_equity`: **+0.818 BB/deal**, 95% CI **[-0.026, +1.662] BB/deal** -> **CHOP** (3.75s / 4.31s bank, 0 errors across 6,908 calls).
  - **CFR Mathematical & Empirical Audit**:
    - Generic ES-MCCFR engine verified against analytical Kuhn Poker via backward-induction best response calculator: Analytical game value $-0.05556$, measured $-0.05554$, NashConv $0.00488$, exploitability $0.00244$.
    - Trained 50,000 iterations of Short Deck PLO5 ES-MCCFR -> `assets/cfr_blueprint_50k.pkl` (111,249 InfoSets).
    - Held-out coverage audit on 1,000 hands: **100.0% lookup coverage (0.0% fallback)** across all streets.
    - Abstraction bottleneck identified: despite 100% coverage, coarse bucketing (8 preflop / 10 postflop) loses critical Omaha 2+3 redraws and blocker subtleties; `CFRBot_50k` lost head-to-head to heuristic policies (-4.66 BB/deal) and scored 6.5/12 points.
  - **Evaluation Record Reconciled**:
    - Recomputed Milestone B `CFRBot_10k` points directly from raw verdicts: 4 wins, 7 chops, 1 loss = 7.5 / 12 points (62.5%), correcting the historical 6.5 typo.
- **Implemented but Unverified / Outstanding**:
  - Container build via `tools/check_build.sh`: Docker CLI 29.2.1 installed, but Docker Desktop engine is not running on host (`pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`). Containerized image build marked **outstanding**.
- **Blocked**: None.

## 3. Architecture Map
- `agent.py`: Submission entry point at project root (`TeamAntigravity / RangeAware_v2`).
- `runtime/`:
  - `range_aware_policy.py`: `RangeAwarePolicy` (`RangeAware_v2`), featuring Bayesian opponent aggression tracking, likelihood-weighted range conditioning, and continuation equity modeling.
  - `policy.py`: `HeuristicPolicy` (`EquityBot_v1` - frozen immediate rollback).
  - `features.py`: `omaha_best_score` (handles 3, 4, 5 board cards), preflop quality heuristics, sampled Monte Carlo equity.
  - `cfr_policy.py`: `CFRPolicy` querying average strategy tables from trained blueprints.
  - `hybrid_policy.py`: Experimental hybrid policy blending CFR defense with heuristic value extraction.
  - `opponent.py`: Within-half memory tracking.
- `training/`:
  - `generic_mccfr.py`: Game-agnostic ES-MCCFR engine implementing `ExtensiveGame` protocol.
  - `kuhn_exact.py`: Kuhn game adapter and exact backward-induction Best-Response / NashConv calculator.
  - `abstraction.py`: Card bucketing (10 preflop, 10 postflop) and infoset key hashing.
  - `mccfr.py`: PLO5 external-sampling MCCFR trainer.
  - `train.py`: CLI driver for offline CFR training.
  - `audit_coverage.py`: Audits hit rate and fallback distribution on held-out deals.
- `opponents/`:
  - `baselines.py`: Complete 12-opponent population (CheckFold, CallingStation, Random, AlwaysRaise, GuideCheapCall, EquityCall, SizeAwareEquity, ActionConditionedRange, AdaptiveExploiter, TellExploiter, CheckAttacker, FrozenEquityBotAttacker).
  - `serve_opponent.py`: Standalone HTTP server for isolated match testing of any registered opponent.
- `evaluation/`:
  - `local_match.py`: In-process duplicate simulator replicating exact judge scoring.
  - `summary_table.py`: Programmatic score calculator and Markdown table generator.
  - `diagnose_losses.py`: Hand-by-hand diagnostic tracing of chip loss contexts.
  - `benchmark_candidates.py`: Side-by-side comparative benchmarking against 12-opponent suite with raw JSON export.
  - `run_critical_multiseed_evaluation.py`: 5-seed 1,000-deal duplicate runner across critical opponents.
  - `run_full_tournament_match.py`: Multi-process HTTP runner with fresh process restart per half.
- `reports/`:
  - `milestone_a_report.md`: Initial architecture and screening benchmark.
  - `milestone_b_report.md`: Full-length tournament validation, CFR audit, and opponent population.
  - `milestone_c_report.md`: Range-aware candidate, multi-seed evaluation, and complete CFR audit.
  - `raw_matches/`: Complete raw judge JSON files.

## 4. Decisions Log
- **DEC-001**: Clean separation of FastAPI plumbing from strategy code in `runtime/`.
- **DEC-002**: Monte Carlo hand strength sampling (80-100 samples) rather than full enumeration (~0.5ms vs 50ms).
- **DEC-003**: In-process local match runner replicating judge_engine scoring for rapid iteration.
- **DEC-004**: Strict isolation of all within-half learning in `memory` dict (no global leaks).
- **DEC-005**: Generalized `omaha_best_score` to evaluate exactly 2 hole + 3 board cards for flop, turn, and river.
- **DEC-006**: Stage official tournament referee files (`game.py`, `evaluator.py`, `judge_engine.py`, `requirements.txt`, etc.) at project root to ensure `test_agent.py` and Docker build context match submission.
- **DEC-007**: Retain `EquityBot_v1` as baseline rollback candidate based on empirical benchmark evidence.
- **DEC-008**: Build `RangeAware_v2` with Bayesian opponent raise frequency estimation ($\hat{r} = (R+2)/(N+10)$) to eliminate maniac exploitation while accurately narrowing ranges against normal and tight players.
- **DEC-009**: Isolate continuation range equity from current range equity to prevent value-betting into hands that only call when ahead.
- **DEC-010**: Promote `RangeAware_v2` to active tournament entry point (`agent.py`) following 100% win rate across 5-seed 1,000-deal critical benchmarks (30W-0C-0L) and official HTTP tournament validation (+2.16 BB/deal vs action_conditioned_range). Keep `EquityBot_v1` frozen in `runtime/policy.py` as immediate verified rollback.

## 5. Skills Catalog
- `.agents/skills/verify-poker-rules/SKILL.md`: Validates ranking, 2+3 selection, raise caps, and rules (Usable).
- `.agents/skills/evaluate-poker-candidate/SKILL.md`: Runs local benchmark suite and official HTTP matches (Usable).
- `.agents/skills/profile-poker-runtime/SKILL.md`: Measures cold start, decision latency, and time bank consumption (Usable).
- `.agents/skills/run-poker-training/SKILL.md`: Offline CFR/response training pipeline (Usable).
- `.agents/skills/export-poker-release/SKILL.md`: Packaging, smoke tests, and Docker verification (Usable).
- `.agents/skills/maintain-project-memory/SKILL.md`: Reconciles persistent project state in MEMORY.md (Usable).

## 6. Best Working Candidate
- **Identifier**: `RangeAware_v2`
- **Entry Point**: `agent.py` at root
- **Participant Name**: `TeamAntigravity`
- **Agent Name**: `RangeAware_v2`
- **Core Modules**: `runtime/features.py`, `runtime/range_aware_policy.py`, `runtime/opponent.py`
- **Rollback Version**: `EquityBot_v1` (`runtime/policy.py`)
- **Measured Evidence**:
  - Multi-seed benchmark (5 seeds x 1,000 deals, 60,000 hands): **30.0 / 30.0 points (100.0% win rate)** vs EquityBot's 24.5/30 (81.7%).
  - Official HTTP 1,000-deal tournament match: **+2.164 BB/deal** (95% CI [+1.516, +2.812]) vs `action_conditioned_range` (`AGENT1_WIN`).
  - Official HTTP 1,000-deal tournament match: **+2.750 BB/deal** (95% CI [+1.230, +4.270]) vs `always_raise` (`AGENT1_WIN`).
  - Suite screening: **9.5 / 12.0 points (79.2%)** with 0 losses.
  - Time bank usage: 3.40s - 5.08s of 8.0s per half (< 65% bank utilized).
  - Reliability: 0 operational errors across > 25,000 total HTTP requests.

## 7. Resume Instructions
- Run unit and official tests: `.\venv\Scripts\python.exe -m pytest tests -v`
- Run 12-opponent comparative benchmark: `.\venv\Scripts\python.exe evaluation\benchmark_candidates.py --deals 100`
- Run 5-seed 1,000-deal critical benchmark: `.\venv\Scripts\python.exe evaluation\run_critical_multiseed_evaluation.py`
- Run official full-length HTTP match: `.\venv\Scripts\python.exe evaluation\run_full_tournament_match.py --agent1 agent.py --agent2 opponents\serve_opponent.py --opp-bot action_conditioned_range --deals 1000 --seed test_seed`
