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
- **Independently Verified & Tested (Milestone F - Review Resolution & Draw-Aware Release)**:
  - **Leading Candidate**: `DrawAware_v1` (`agent.py` at root, core logic in `runtime/draw_aware_policy.py`).
  - **Rollback Baseline 1**: `RangeAware_v2` (frozen in `runtime/range_aware_policy.py`, commit `6be5da6c9610a844bb3f19179c98e9b462174274`).
  - **Rollback Baseline 2**: `EquityBot_v1` (frozen in `runtime/policy.py`).
  - **Unit, Official, Agreement, and Regression Tests**: **64 / 64 PASSED** cleanly across `tests/`.
  - **Systematic Resolution of Code Review Findings (F1–F9)**:
    - **F1 (Flop/turn draw blindness)**: Created `runtime/draw_aware_policy.py` sampling joint deals (5 opponent cards + `5 - len(board)` future runout cards) from the unseen deck. Retained current made-hand score strictly for past-action likelihood weighting (no future lookahead bias). Verified on regression test `As Ks Qh Jh 9c` / flop `Ts 8s 6d` (calling 26 into 134): `RangeAware_v2` gave 0.29% made-hand win share and folded; `DrawAware_v1` gave 56.9% showdown equity and called (agrees with brute-force reference within ±2%).
    - **F2 (RNG state leak across halves)**: Implemented `play_local_match_fresh` accepting factory callables to ensure fresh policy instances per half. Updated `tests/test_harness_agreement.py` to kill and re-spawn fresh server subprocesses between halves. Verified 0 divergences across all actions, nets, paired differences, and final CI.
    - **F3 (Opponent callback gaps)**: Wired `bot.new_half` invocation in `/new-half`, batched `hand_results` delivery in `/act` before `choose_action`, and `on_hand_end` delivery in `/hand-end` in `opponents/serve_opponent.py`. Verified via `TestClient`.
    - **F4 (Ablation API mismatch)**: Fixed parameter names and unpacking in `runtime/ablations.py`. Restored `preflop_hand_quality` for `EquityOnly` preflop decisions. Ablation experiments re-raise unexpected internal exceptions.
    - **F5 (CFR unweighted strategy accumulation)**: Updated `GenericMCCFRTrainer.traverse` to accumulate strategy weighted by the player's own reach probability (`reach_prob * strat[a]`), conforming to Lanctot et al. 2009 (Algorithm 2). Verified on unequal-reach sequential game.
    - **F6 (Incomplete checkpoints)**: Added `regrets` and `rng_state` to checkpoint serialization in `training/generic_mccfr.py`. Verified exact bit-for-bit resume equivalence between uninterrupted N+M training and split N then M training.
    - **F7 (Internal exception opacity)**: Added `_internal_exceptions` and `_illegal_action_fallbacks` counters in `MEMORY` and exposed in `GET /`.
    - **F8 (Time bank estimation drift)**: `agent.py` `route_act` measures elapsed time over full POST request and accumulates `_charged_bank_spent` using `max(0.0, elapsed - 0.001)`. Policy dynamic budgeting checks this request-level metric.
    - **F9 (Opponent action selection bias)**: Documented observation constraints; separated past-action likelihoods strictly from future card sampling.
  - **Shared Generic MCCFR Engine Evaluated on Analytical Kuhn Ground Truth**:
    - `GenericMCCFRTrainer` trained directly on `KuhnGame` converged to **0.016 NashConv exploitability**: Queen checks at root 99.6%, Jack folds facing bet 99.98%, King calls facing bet 99.93%.
  - **Head-to-Head Candidate Comparison (10 Matches, 5,000 deals, 10,000 hands per candidate)**:
    - Overall points: `DrawAware_v1` **8.0 / 10.0 points (mean +3.615 BB/deal)** vs `RangeAware_v2` **8.0 / 10.0 points (mean +3.053 BB/deal)** (+0.562 BB/deal overall lead).
    - Massive outperformance vs `street_inversion_attacker`: **+5.571 BB/deal** vs **+3.411 BB/deal** (+2.160 BB/deal gain).
    - Massive outperformance vs independent `draw_aware_opponent`: **+0.635 BB/deal** vs **+0.046 BB/deal** (+0.589 BB/deal gain).
  - **Official Container Verification (`tools/check_build.sh`) Fully Verified**:
    - Image adds only **35 MB** on top of base image (cap: 3,072 MB).
    - Restricted container smoke test (`--cpus 1`, `--memory 4g`, read-only FS, `--network none`):
      - Startup: `GET / answered after 1.0 s` (well below 15.0s budget).
      - Action Latencies: Preflop 0–1 ms, flop 2–3 ms, river 1 ms.
      - Result: **SMOKE TEST PASSED. ALL CHECKS PASSED.**
  - **Full-Length 1,000-Deal Restricted Container Tournament Matches (2,000 hands each, fresh container restart per half)**:
    - Vs `action_conditioned_range` (`seed = official_container_acr_draw_aware`): **+10.483 BB/deal** (95% CI **[+9.532, +11.435] BB/deal**, sample std dev 15.36) -> **AGENT1_WIN** (+20,967 chips, Half 1 bank **5.69s / 8.00s**, Half 2 bank **5.88s / 8.00s**, **0 calls skipped**, **0 errors**, **0 exceptions**, **0 fallbacks** across 8,001 total requests).
    - Vs `street_inversion_attacker` (`seed = official_container_inversion_draw_aware`): **+9.444 BB/deal** (95% CI **[+8.520, +10.368] BB/deal**, sample std dev 14.91) -> **AGENT1_WIN** (+18,888 chips, Half 1 bank **6.63s / 8.00s**, Half 2 bank **7.47s / 8.00s**, **0 calls skipped**, **0 errors**, **0 exceptions**, **0 fallbacks** across 8,004 total requests).
  - **Review Bundles Exported**:
    - `release/review_bundle_DrawAware_v1.zip` (187 files, 1.65 MB uncompressed, 0.45 MB zip) containing full updated candidate, regression tests, and match records.
    - `release/review_bundle_RangeAware_v2.zip` (preserved fallback archive from commit `6be5da6`).
- **Implemented but Unverified / Outstanding**: None.
- **Remaining Limitations**:
  - Offline MCCFR blueprint training is constrained by 5-card PLO combinatorial state space; active candidate relies on joint-deal Monte Carlo runout modeling with dynamic time budgeting rather than full precomputed equilibrium tables.
  - Runtime time bank tracking measures full POST request processing on host and container loopback; external network hop latency before reaching container port is not observable by the agent process.
- **Blocked**: None.

## 3. Architecture Map
- `agent.py`: Submission entry point at project root (`TeamAntigravity / DrawAware_v1`).
- `runtime/`:
  - `draw_aware_policy.py`: `DrawAwarePolicy` (`DrawAware_v1`), featuring joint-deal Monte Carlo runout rollouts, past-action likelihood conditioning on visible made-hand scores (no future card lookahead bias), dynamic time budgeting, protected checking, and continuation filtering.
  - `range_aware_policy.py`: `RangeAwarePolicy` (`RangeAware_v2` - preserved immediate rollback baseline).
  - `policy.py`: `HeuristicPolicy` (`EquityBot_v1` - secondary rollback baseline).
  - `ablations.py`: Isolated ablation policies (`EquityOnly`, `RangeOnly`, `RangeAndAdapt`, `Complete_v2`).
  - `features.py`: `omaha_best_score`, `omaha_score_fast`, `precompute_board_masks`, `preflop_hand_quality`.
  - `opponent.py`: Within-half memory tracking.
- `training/`:
  - `generic_mccfr.py`: Game-agnostic ES-MCCFR engine with reach-weighted strategy accumulation and full state checkpointing.
  - `kuhn_exact.py`: Kuhn game adapter and exact backward-induction Best-Response / NashConv calculator.
  - `abstraction.py`: Card bucketing (10 preflop, 10 postflop) and infoset key hashing.
  - `mccfr.py`: PLO5 external-sampling MCCFR trainer delegating to `GenericMCCFRTrainer`.
- `opponents/`:
  - `draw_aware_opponent.py`: Independent draw-aware benchmark opponent.
  - `baselines.py`: Complete baseline opponent population.
  - `adversarial.py`: 10 targeted stress-test opponents including `DrawAwareOpponent`.
  - `serve_opponent.py`: Standalone HTTP server for isolated match testing with full lifecycle callbacks (`new_half`, `hand_results`, `on_hand_end`).
- `evaluation/`:
  - `local_match.py`: In-process duplicate simulator with `play_local_match_fresh` supporting fresh policy instances per half.
  - `compare_draw_aware.py`: Head-to-head comparison runner between `RangeAware_v2` and `DrawAware_v1`.
  - `run_full_tournament_match.py`: Multi-process HTTP and Docker container runner with fresh container restart per half.
  - `profile_http_runtime.py`: Measures exact charged time bank (`sum(max(0, req - 0.001))`) over complete HTTP requests.
- `release/`:
  - `review_bundle_DrawAware_v1.zip`: Current reviewable release bundle (187 files, 0.45 MB zip).
  - `review_bundle_RangeAware_v2.zip`: Preserved fallback release bundle (commit `6be5da6`).
- `reports/`:
  - `milestone_f_report.md`: Complete report on review resolution, evaluation integrity, and `DrawAware_v1` container validation.
  - `raw_matches/`: Raw JSON records of official container matches and benchmark runs.

## 4. Decisions Log
- **DEC-001** through **DEC-013**: Historical architecture, heuristics, CFR unification, and continuation filter decisions (see `docs/DECISIONS.md`).
- **DEC-014**: Resolution of Evaluation Integrity Defects (F2 fresh process per half, F3 opponent callbacks, F4 ablation API).
- **DEC-015**: Joint-Deal Monte Carlo Runout Modeling in DrawAware_v1 (F1 resolution).
- **DEC-016**: Reach-Weighted Strategy Accumulation and Resumable Checkpoints in ES-MCCFR (F5, F6 resolution).
- **DEC-017**: Comprehensive Request-Level Charged Time Tracking and Internal Instrumentation (F7, F8 resolution).
- **DEC-018**: Promotion of `DrawAware_v1` as Active Tournament Candidate with Multi-Tier Rollbacks.

## 5. Best Working Candidate
- **Identifier**: `DrawAware_v1`
- **Entry Point**: `agent.py` at root
- **Participant Name**: `TeamAntigravity`
- **Agent Name**: `DrawAware_v1`
- **Core Modules**: `runtime/draw_aware_policy.py`, `runtime/features.py`, `runtime/opponent.py`
- **Rollback Version 1**: `RangeAware_v2` (`runtime/range_aware_policy.py`, commit `6be5da6`)
- **Rollback Version 2**: `EquityBot_v1` (`runtime/policy.py`)
- **Measured Evidence**:
  - **Full-Length 1,000-Deal Restricted Container Tournament Matches (Official Judge Engine, 1 CPU, 4GB RAM, read-only FS, fresh container restart per half)**:
    - Vs `action_conditioned_range` (`seed = official_container_acr_draw_aware`): **+10.483 BB/deal** (95% CI **[+9.532, +11.435] BB/deal**, sample std dev 15.36) -> **AGENT1_WIN** (+20,967 chips, Half 1 bank **5.69s / 8.00s**, Half 2 bank **5.88s / 8.00s**, **0 calls skipped**, **0 errors**, **0 exceptions**, **0 fallbacks** across 8,001 total calls).
    - Vs `street_inversion_attacker` (`seed = official_container_inversion_draw_aware`): **+9.444 BB/deal** (95% CI **[+8.520, +10.368] BB/deal**, sample std dev 14.91) -> **AGENT1_WIN** (+18,888 chips, Half 1 bank **6.63s / 8.00s**, Half 2 bank **7.47s / 8.00s**, **0 calls skipped**, **0 errors**, **0 exceptions**, **0 fallbacks** across 8,004 total calls).
  - Head-to-head comparison (10 matches x 500 duplicate deals, 20,000 hands total): **8.0 / 10.0 points (mean +3.615 BB/deal)** vs `RangeAware_v2`'s +3.053 BB/deal (+0.562 BB/deal lead; +2.16 BB/deal vs inversion, +0.59 BB/deal vs independent DrawAwareOpponent).
  - Official Container Runtime & Size (`tools/check_build.sh`): Startup 1.0s / 15.0s; added size 35 MB / 3,072 MB cap; action latency 0-3 ms across all legal contexts; 0 errors across all requests.

## 6. Resume Instructions
- Run full test suite: `.\venv\Scripts\python.exe -m pytest tests -v`
- Run harness agreement audit: `.\venv\Scripts\python.exe tests\test_harness_agreement.py`
- Run evaluation integrity regression suite: `.\venv\Scripts\python.exe -m pytest tests/test_evaluation_integrity.py -v`
- Run candidate comparison: `.\venv\Scripts\python.exe evaluation\compare_draw_aware.py`
- Run exact HTTP runtime profiler: `.\venv\Scripts\python.exe evaluation\profile_http_runtime.py`
- Run official container build check: `bash tools/check_build.sh`
- Re-export review bundle: `.\venv\Scripts\python.exe tools\export_review_bundle.py`
- Run official full-length container match: `.\venv\Scripts\python.exe evaluation\run_full_tournament_match.py --container --opp-bot action_conditioned_range --deals 1000 --seed test_seed`
