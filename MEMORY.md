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
- **Independently Verified & Qualified (Milestone G - Counterplay_v3 Release)**:
  - **Leading Release Candidate**: `Counterplay_v3` (`agent.py` at root, core logic in `runtime/counterplay_policy.py`, `runtime/dense_equity.py`, lookup tables in `data/preflop.npy` and `data/pair_triple.npy`, frozen config in `data/policy_config.json`).
  - **Docker Image Digest**: `sha256:014fa99812add00e1bcb3c7a8144139fcf7b647f950c505f56249b5569a57a84` (`poker-agent-check:latest`).
  - **Git Branch**: `counterplay-v3-integration`.
  - **Rollback Baseline 1**: `DrawAware_v1` (preserved in `opponents/agent_drawaware_v1.py` and `release/review_bundle_DrawAware_v1.zip`, commit `a1debba524ce439fcacaec8ff45509140234a15b`).
  - **Rollback Baseline 2**: `RangeAware_v2` (frozen in `runtime/range_aware_policy.py`, commit `6be5da6c9610a844bb3f19179c98e9b462174274`).
  - **Rollback Baseline 3**: `EquityBot_v1` (frozen in `runtime/policy.py`).
  - **Asset Provenance Verification**: All 6 candidate assets verified bit-for-bit against `PROVENANCE.json` SHA-256 hashes.
  - **Tests Status**: **16 / 16 package tests PASSED**, **68 / 68 unit/integration tests PASSED** in 13.72s.
  - **Official Container Verification (`tools/check_build.sh`)**:
    - Image adds 82 MB on base (cap: 3,072 MB).
    - Cold start: 1.0s / 15.0s budget over HTTP.
    - Smoke test: PASSED. ALL CHECKS PASSED.
  - **Full 1,000-Deal Restricted Docker Qualification Matches (18,000 Hands)**:
    - Executed with 1 CPU, 4 GB RAM, read-only FS, 512MB tmpfs, dropped caps, fresh container per half.
    - vs **Timecasters** (`a61a1388f24c6495695d40be5026479266afb818`): **2.5 / 3.0 pts (83.3%)**, mean **+0.858 BB/deal** (1 Chop, 2 Wins).
    - vs **TwoStack** (`8f4fbc964c0d2814c36cd3455f25a379e0cf6f66`): **3.0 / 3.0 pts (100.0%)**, mean **+1.278 BB/deal** (3 Wins).
    - vs **vsmBOT** (`22330246ecb2143b9256204b106473bdfdeaa7a1`): **3.0 / 3.0 pts (100.0%)**, mean **+2.192 BB/deal** (3 Wins).
    - **Total Container Qualification Score: 8.5 / 9.0 match points (94.4%)**, **+1.442 BB/deal mean**.
    - **Operational Reliability**: **0 judge errors, 0 internal exceptions, 0 fallbacks, 0 timeouts across 69,802 container requests**.
    - **Bank Time**: Max thinking bank used was **4.67s / 8.00s limit** (average ~3.3s).
  - **Matched Comparison vs Preserved DrawAware_v1 Baseline**:
    - `DrawAware_v1` achieved only 3.0 / 9.0 points (33.3%), losing all 6 matches to Timecasters and TwoStack (-1.571 BB/deal overall mean).
    - `Counterplay_v3` achieved a **+3.014 BB/deal paired advantage** across all 9 matched seeds, strictly reversing all 6 losses into 5 wins and 1 chop.
  - **Broader Style Evaluation (Container Matches, 8,000 Hands)**:
    - vs `check_fold`: **+1.475 BB/deal** (WIN, 1.0 pt, CI [+1.46, +1.49])
    - vs `calling_station`: **+11.906 BB/deal** (WIN, 1.0 pt, CI [+10.84, +12.97])
    - vs `random`: **+6.745 BB/deal** (WIN, 1.0 pt, CI [+5.32, +8.17])
    - vs `always_raise`: **+6.658 BB/deal** (WIN, 1.0 pt, CI [+5.01, +8.31])
    - Overall: **4.0 / 4.0 points (100%)**, mean **+6.696 BB/deal**.
  - **Resource Telemetry**:
    - Latency: Mean 1.06 ms, P50 1.00 ms, P95 1.51 ms, P99 1.84 ms, Max 2.80 ms (< 1,000.0 ms limit).
    - Memory: 74.54 MiB RSS / 4,096 MiB (1.82% utilization, >4,020 MiB headroom).
  - **Exported Review Bundles**:
    - `release/review_bundle_Counterplay_v3.zip` (287 files, 24.51 MB uncompressed, 2.56 MB zip).
    - `release/review_bundle_DrawAware_v1.zip` (preserved rollback archive).

## 3. Architecture Map
- `agent.py`: Submission entry point at project root (`TeamAntigravity / Counterplay_v3`).
- `data/`:
  - `preflop.npy`: 376,992 holding suit-invariant preflop equity table (4.52 MB).
  - `pair_triple.npy`: Dense rank index lookup table for 2-hole/3-board evaluation (17.99 MB).
  - `policy_config.json`: Frozen hyperparameters and threshold configuration.
- `runtime/`:
  - `counterplay_policy.py`: `CounterplayPolicy` (`Counterplay_v3`), featuring precomputed preflop equity lookups, 256 joint postflop runout worlds sampled via NumPy, opponent adaptation, protected check-trapping, and dynamic bet sizing.
  - `dense_equity.py`: Vectorized 2-hole/3-board lookup evaluation engine.
  - `draw_aware_policy.py`: `DrawAwarePolicy` (`DrawAware_v1` - primary rollback baseline).
  - `range_aware_policy.py`: `RangeAwarePolicy` (`RangeAware_v2` - secondary rollback baseline).
  - `policy.py`: `HeuristicPolicy` (`EquityBot_v1` - tertiary rollback baseline).
  - `ablations.py`: Isolated ablation policies.
  - `features.py`: Feature extractors and Omaha evaluation helpers.
  - `opponent.py`: Within-half memory tracking.
- `opponents/`:
  - `agent_drawaware_v1.py`: Preserved `DrawAware_v1` baseline server for matched evaluations.
  - `baselines.py`: Canonical opponent population (`check_fold`, `calling_station`, `random`, `always_raise`, etc.).
  - `adversarial.py`: Targeted stress-test opponents.
  - `serve_opponent.py`: Standalone HTTP server for isolated match testing with full lifecycle callbacks.
- `opponents_external/`:
  - `timecasters/agent.py`: Pinned Timecasters bot (commit `a61a1388`).
  - `twostack/agent.py`: Pinned TwoStack bot (commit `8f4fbc96`).
  - `vsm/agent.py`: Pinned vsmBOT (commit `22330246`).
- `evaluation/`:
  - `run_full_tournament_match.py`: Multi-process HTTP and restricted Docker container runner with fresh container restart per half.
  - `run_docker_qualification.py`: Comprehensive automated qualification runner for external bots, matched baselines, and broader styles.
  - `local_match.py`: In-process duplicate simulator with fresh half support.
- `release/`:
  - `review_bundle_Counterplay_v3.zip`: Active candidate release bundle.
  - `review_bundle_DrawAware_v1.zip`: Preserved rollback bundle.
- `reports/`:
  - `milestone_g_report.md`: Detailed qualification report for `Counterplay_v3`.
  - `docker_qualification_results.json`: Complete machine-readable record of all qualification matches and paired deltas.
  - `raw_matches/`: Raw JSON records of official container matches.

## 4. Decisions Log
- **DEC-001** through **DEC-017**: Historical architecture, heuristics, CFR unification, and bug resolutions (see `docs/DECISIONS.md`).
- **DEC-018**: Promotion of `DrawAware_v1` as Active Tournament Candidate (superseded by DEC-019).
- **DEC-019**: Promotion of `Counterplay_v3` as Tournament Release Candidate.

## 5. Best Working Candidate
- **Identifier**: `Counterplay_v3`
- **Entry Point**: `agent.py` at root
- **Participant Name**: `TeamAntigravity`
- **Agent Name**: `Counterplay_v3`
- **Core Modules**: `runtime/counterplay_policy.py`, `runtime/dense_equity.py`, `data/preflop.npy`, `data/pair_triple.npy`, `data/policy_config.json`
- **Rollback Version 1**: `DrawAware_v1` (`opponents/agent_drawaware_v1.py`, `release/review_bundle_DrawAware_v1.zip`, commit `a1debba`)
- **Rollback Version 2**: `RangeAware_v2` (`runtime/range_aware_policy.py`, commit `6be5da6`)
- **Rollback Version 3**: `EquityBot_v1` (`runtime/policy.py`)

## 6. How to Run & Verify
```powershell
# 1. Run unit and integration tests (68 tests)
.\venv\Scripts\python.exe -m pytest -q

# 2. Run official container build and smoke test
bash tools/check_build.sh

# 3. Run full qualification suite across all opponents and seeds
python evaluation/run_docker_qualification.py --phase all
```
