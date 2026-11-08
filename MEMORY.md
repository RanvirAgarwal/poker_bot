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
- **Implemented & Tested**:
  - `agent.py`: Tournament web server entry point (FastAPI) with health check, /new-half, /act, /hand-end
  - `runtime/features.py`: Preflop card properties, general `omaha_best_score` (flop/turn/river), Monte Carlo equity sampling
  - `runtime/policy.py`: `HeuristicPolicy` (equity estimation, pot odds, position, SPR-aware sizing, mixed frequencies)
  - `runtime/opponent.py`: Within-half opponent tendency tracking in judge memory dict
  - `opponents/baselines.py`: CheckFold, CallingStation, Random, AlwaysRaise, EquityCall
  - `evaluation/local_match.py`: Fast duplicate match simulator with exact judge_engine scoring
  - `evaluation/run_benchmark.py`: Local benchmarking runner across all baseline opponents
  - `evaluation/run_official_match.py`: Official duplicate match runner using `judge_engine.py` over HTTP
  - `tests/test_rules.py`: 19 tests verifying Short Deck rankings, Omaha 2+3 rules, game mechanics, determinism
  - `tests/test_agent_protocol.py`: 5 tests verifying agent HTTP protocol conformance
  - Skills catalog: 6 project skills under `.agents/skills/`
- **Implemented but Unverified**:
  - Full Docker build via `tools/check_build.sh` (requires Docker daemon on host)
- **Planned**:
  - CFR training infrastructure (`training/train_cfr.py`) for abstraction and blueprint solving
  - Opponent response exploitation modeling
- **Blocked**: None

## 3. Architecture Map
- `agent.py`: Thin FastAPI wrapper; translates HTTP to dataclasses, invokes `runtime/`, returns safe fallback on error
- `runtime/`:
  - `features.py`: Pure observation-to-feature transforms; `omaha_best_score` handles 3, 4, 5 board cards
  - `policy.py`: Decision logic; combines hand equity, pot odds, position, and legal action masks
  - `opponent.py`: Per-half opponent statistics stored exclusively in `memory` dict
- `evaluation/`:
  - `local_match.py`: In-process duplicate simulator (no HTTP socket dependency, runs inside standard sandbox)
  - `run_benchmark.py`: High-throughput screening suite against baseline registry
  - `run_official_match.py`: Multi-process orchestrator using official `judge_engine.py`
- `opponents/`: Independent opponent bot implementations for testing
- `tests/`: Pytest rule and protocol test suites
- `docs/`: `ARCHITECTURE.md` and `DECISIONS.md`

## 4. Decisions
- **DEC-001**: Clean separation of FastAPI plumbing from strategy code in `runtime/`
- **DEC-002**: Monte Carlo hand strength sampling (100 samples) rather than full C(26,5)=65,780 enumeration (~0.5ms vs 50ms)
- **DEC-003**: In-process local match runner replicating judge_engine scoring for rapid iteration
- **DEC-004**: Strict isolation of all within-half learning in `memory` dict (no global leaks)
- **DEC-005**: Generalized `omaha_best_score` to evaluate exactly 2 hole + 3 board cards for flop, turn, and river

## 5. Skills Catalog
- `.agents/skills/verify-poker-rules/SKILL.md`: Validates ranking, 2+3 selection, raise caps, and rules (Usable)
- `.agents/skills/evaluate-poker-candidate/SKILL.md`: Runs local benchmark suite and official HTTP matches (Usable)
- `.agents/skills/profile-poker-runtime/SKILL.md`: Measures cold start, decision latency, and time bank consumption (Usable)
- `.agents/skills/run-poker-training/SKILL.md`: Offline CFR/response training pipeline (Planned)
- `.agents/skills/export-poker-release/SKILL.md`: Packaging, smoke tests, and Docker verification (Usable)
- `.agents/skills/maintain-project-memory/SKILL.md`: Reconciles persistent project state in MEMORY.md (Usable)

## 6. Experiments and Findings
- **Benchmark Suite (100 deals duplicate = 200 hands each)**:
  - Vs `check_fold`: **+1.360 BB/deal**, 95% CI [+1.26, +1.46] -> **AGENT1_WIN** (0 errors, 4,828 hands/s)
  - Vs `calling_station`: **+11.210 BB/deal**, 95% CI [+8.36, +14.06] -> **AGENT1_WIN** (0 errors, 467 hands/s)
  - Vs `random`: **+7.060 BB/deal**, 95% CI [+2.08, +12.04] -> **AGENT1_WIN** (0 errors, 1,455 hands/s)
  - Vs `always_raise`: **+8.590 BB/deal**, 95% CI [+4.65, +12.53] -> **AGENT1_WIN** (0 errors, 1,634 hands/s)
  - Vs `equity_call`: **+2.900 BB/deal**, 95% CI [+1.13, +4.67] -> **AGENT1_WIN** (0 errors, 397 hands/s)
- **Official judge_engine HTTP Match (50 deals duplicate)**:
  - Vs `baseline_calling_station`: **+14.300 BB/deal**, 95% CI [+10.19, +18.41] -> **AGENT1_WIN** (1.0 - 0.0 pts)
  - Thinking time used: 0.06s of 8.00s time bank (<1% of budget); 0 errors; 179 hands/s over full HTTP
- **Cold Start Warmup**:
  - `evaluator.warmup()` generates 376,992-hand lookup table in **0.134 seconds** (far below 15s limit)

## 7. Best Working Candidate
- **Identifier**: `EquityBot_v1` (Milestone A)
- **Entry Point**: `agent.py` at root
- **Participant Name**: `TeamAntigravity`
- **Agent Name**: `EquityBot_v1`
- **Core Modules**: `runtime/features.py`, `runtime/policy.py`, `runtime/opponent.py`
- **Measured Evidence**: Undefeated across all 5 baselines in screening (5/5 wins); official judge_engine win (+14.30 BB/deal vs CallingStation); 0 operational errors.
- **Known Weaknesses**: Heuristic threshold boundaries are static; does not yet compute full game-theoretic Nash equilibrium (CFR).
- **Rollback Instructions**: Git checkout commit tagging Milestone A baseline.

## 8. Active Work
- Milestone A completed and verified.
- Milestone B/C: CFR blueprint abstraction and training pipeline.

## 9. Resume Instructions
- Run rule tests: `.\venv\Scripts\python.exe -m pytest tests\test_rules.py -v`
- Run protocol tests: `.\venv\Scripts\python.exe -m pytest tests\test_agent_protocol.py -v`
- Run screening benchmark: `.\venv\Scripts\python.exe evaluation\run_benchmark.py 100`
- Run official judge match: `.\venv\Scripts\python.exe evaluation\run_official_match.py 50 baseline-bots/baseline_calling_station.py`
