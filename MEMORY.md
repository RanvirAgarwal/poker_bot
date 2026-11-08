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
  - Loader Audit: Staged official referee files at project root; verified `tests/test_agent_official.py` executes our candidate `C:\Users\ranvi\poker_bot\agent.py` (`TeamAntigravity / EquityBot_v1`), passing **12/12 official tests**.
  - Rule Mechanics: 19 unit tests in `tests/test_rules.py` verifying Short Deck rankings, Omaha selection, and state transitions -> **19/19 PASSED**.
  - CFR Theory Audit: Mathematical validation on Kuhn Poker against exact analytical Nash equilibrium ($V_1^* \to -1/18$, Queen checks, Jack folds, King calls) in `tests/test_cfr_correctness.py` -> **4/4 PASSED**.
  - CFR Coverage Audit: Evaluated on 500 held-out deals (1,000 hands):
    - 2k checkpoint (`cfr_blueprint_v1.pkl`, 48k infosets): 97.1% coverage (81.1% on River).
    - 10k checkpoint (`cfr_blueprint_10k.pkl`, 84k infosets): **99.5% coverage (96.2% on River, 0.5% overall fallback)**.
  - Full-Length 1,000-Deal Tournament Matches (2,000 hands total with fresh server restart between halves):
    - Vs `CallingStation`: **+12.018 BB/deal**, 95% CI [+11.033, +13.004] -> **AGENT1_WIN** (Half 1 time 3.43s, Half 2 time 1.31s, 0 errors / 8,001 requests).
    - Vs `RandomBot`: **+8.473 BB/deal**, 95% CI [+6.842, +10.104] -> **AGENT1_WIN** (Half 1 time 0.79s, Half 2 time 0.52s, 0 errors / 5,279 requests).
  - 12-Opponent Benchmark Suite: Evaluated `EquityBot_v1` (9.0 / 12 points, 75.0%), `HybridPolicy` (7.5 / 12 points), and `CFRBot_10k` (6.5 / 12 points).
- **Implemented but Unverified / Outstanding**:
  - Container build via `tools/check_build.sh`: Docker CLI 29.2.1 installed, but Docker Desktop engine is not running on host (`pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`). Containerized image build marked **outstanding**.
- **Blocked**: None.

## 3. Architecture Map
- `agent.py`: Submission entry point at project root (`TeamAntigravity / EquityBot_v1`).
- `runtime/`:
  - `features.py`: `omaha_best_score` (handles 3, 4, 5 board cards), preflop quality, sampled Monte Carlo equity.
  - `policy.py`: `HeuristicPolicy` (`EquityBot_v1`).
  - `cfr_policy.py`: `CFRPolicy` querying average strategy sums from trained checkpoints.
  - `hybrid_policy.py`: Adaptive hybrid blending CFR defense with calling-station value extraction.
  - `opponent.py`: Within-half memory tracking.
- `training/`:
  - `abstraction.py`: Card bucketing (10 preflop, 10 postflop) and infoset key hashing.
  - `mccfr.py`: External-Sampling Monte Carlo Counterfactual Regret Minimization engine.
  - `train.py`: CLI driver for offline CFR training.
  - `audit_coverage.py`: Audits hit rate and fallback distribution on held-out deals.
- `opponents/baselines.py`: Complete 12-opponent population (CheckFold, CallingStation, Random, AlwaysRaise, GuideCheapCall, EquityCall, SizeAwareEquity, ActionConditionedRange, AdaptiveExploiter, TellExploiter, CheckAttacker, FrozenEquityBotAttacker).
- `evaluation/`:
  - `local_match.py`: In-process duplicate simulator.
  - `run_benchmark.py`: Complete 12-opponent screening benchmark.
  - `run_full_tournament_match.py`: Multi-process HTTP runner with fresh process restart per half.
  - `compare_candidates.py`: Head-to-head candidate comparison.
- `reports/`:
  - `milestone_a_report.md`: Initial architecture and screening benchmark.
  - `milestone_b_report.md`: Full-length tournament validation, CFR audit, and opponent population.
  - `raw_matches/`: Complete raw judge JSON files.

## 4. Decisions Log
- **DEC-001**: Clean separation of FastAPI plumbing from strategy code in `runtime/`.
- **DEC-002**: Monte Carlo hand strength sampling (100 samples) rather than full C(26,5)=65,780 enumeration (~0.5ms vs 50ms).
- **DEC-003**: In-process local match runner replicating judge_engine scoring for rapid iteration.
- **DEC-004**: Strict isolation of all within-half learning in `memory` dict (no global leaks).
- **DEC-005**: Generalized `omaha_best_score` to evaluate exactly 2 hole + 3 board cards for flop, turn, and river.
- **DEC-006**: Stage official tournament referee files (`game.py`, `evaluator.py`, `judge_engine.py`, `requirements.txt`, etc.) at project root to ensure `test_agent.py` and Docker build context match submission.
- **DEC-007**: Retain `EquityBot_v1` as the active tournament entry point based on measured empirical benchmark evidence (9.0/12 pts vs 7.5/12 for Hybrid and 6.5/12 for CFR-10k).

## 5. Skills Catalog
- `.agents/skills/verify-poker-rules/SKILL.md`: Validates ranking, 2+3 selection, raise caps, and rules (Usable).
- `.agents/skills/evaluate-poker-candidate/SKILL.md`: Runs local benchmark suite and official HTTP matches (Usable).
- `.agents/skills/profile-poker-runtime/SKILL.md`: Measures cold start, decision latency, and time bank consumption (Usable).
- `.agents/skills/run-poker-training/SKILL.md`: Offline CFR/response training pipeline (Usable).
- `.agents/skills/export-poker-release/SKILL.md`: Packaging, smoke tests, and Docker verification (Usable).
- `.agents/skills/maintain-project-memory/SKILL.md`: Reconciles persistent project state in MEMORY.md (Usable).

## 6. Experiments & Findings
- **CFR Theory Audit (Kuhn Poker)**:
  - Theoretical analytical value: $-1/18 \approx -0.0556$.
  - ES-MCCFR convergence verified: Player 1 Queen checks at root (>90%), Player 2 Jack folds to bet (>90%), Player 2 King calls bet (>90%).
- **CFR Coverage Progression**:
  - 2,000 iterations: 48,421 infosets; 97.1% overall coverage (18.9% river fallback).
  - 10,000 iterations: 84,492 infosets; **99.5% overall coverage (3.8% river fallback, 0.5% overall fallback)**.
- **Opponent Screening Benchmark (100 duplicate deals each)**:
  - `EquityBot_v1`: **9.0 / 12 points (75.0%)**. Wins: `check_fold` (+1.36 BB), `calling_station` (+11.21 BB), `random` (+7.06 BB), `always_raise` (+8.59 BB), `guide_cheap_call` (+2.72 BB), `equity_call` (+2.50 BB), `adaptive_exploiter` (+2.35 BB). Chops: `size_aware_equity`, `tell_exploiter`, `check_attacker`, `frozen_equity_attacker`. Loss: `action_conditioned_range` (-2.63 BB).
  - `CFRBot_10k`: **6.5 / 12 points (54.2%)**. Chops with `calling_station`, `equity_call`, `size_aware_equity`, `action_conditioned_range`, `adaptive_exploiter`, `check_attacker`, `frozen_equity_attacker`. Wins: `check_fold`, `random`, `guide_cheap_call`, `tell_exploiter`. Loss: `always_raise` (-7.03 BB).
  - `HybridPolicy`: **7.5 / 12 points (62.5%)**.
- **Full-Length Tournament Match (1,000 duplicate deals = 2,000 hands with process restart)**:
  - Vs `CallingStation`: **+12.018 BB/deal**, CI [+11.033, +13.004] -> **AGENT1_WIN** (3.43s / 1.31s bank, 0 errors).
  - Vs `RandomBot`: **+8.473 BB/deal**, CI [+6.842, +10.104] -> **AGENT1_WIN** (0.79s / 0.52s bank, 0 errors).

## 7. Best Working Candidate
- **Identifier**: `EquityBot_v1`
- **Entry Point**: `agent.py` at root
- **Participant Name**: `TeamAntigravity`
- **Agent Name**: `EquityBot_v1`
- **Core Modules**: `runtime/features.py`, `runtime/policy.py`, `runtime/opponent.py`
- **Measured Evidence**: Undefeated in official 1,000-deal tournament matches (+12.02 BB/deal vs CallingStation, +8.47 BB/deal vs RandomBot); 9.0/12 match points across 12-opponent suite; 0 errors out of 13,280+ total requests; charged thinking time < 4.0s / 8.0s per half.
- **Known Weaknesses**: Underestimates opponent range strength against `action_conditioned_range` (loss of -2.63 BB/deal).

## 8. Active Work
- Milestone B verified and completed.
- Next: Refine postflop range conditioning in `EquityBot_v1` to eliminate the loss against `ActionConditionedRangeBot`.

## 9. Resume Instructions
- Run rule tests: `.\venv\Scripts\python.exe -m pytest tests\test_rules.py -v`
- Run official agent tests: `.\venv\Scripts\python.exe -m pytest tests\test_agent_official.py -v`
- Run CFR mathematical audit: `.\venv\Scripts\python.exe -m pytest tests\test_cfr_correctness.py -v`
- Run 12-opponent benchmark: `.\venv\Scripts\python.exe evaluation\run_benchmark.py 100`
- Run full 1,000-deal tournament match: `.\venv\Scripts\python.exe evaluation\run_full_tournament_match.py --agent1 agent.py --agent2 starter\baseline-bots\baseline_calling_station.py --deals 1000 --seed tourn_seed_1`
