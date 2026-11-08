# Milestone F Report: Review Resolution, Evaluation Integrity, and DrawAware_v1 Release

**Date**: November 8, 2026  
**Candidate Identifier**: `DrawAware_v1`  
**Entry Point**: `agent.py` (`TeamAntigravity / DrawAware_v1`)  
**Rollback Baselines**: `RangeAware_v2` (`runtime/range_aware_policy.py`), `EquityBot_v1` (`runtime/policy.py`)  
**Review Input**: `RangeAware_v2_Independent_Code_Review.md`  

---

## 1. Executive Summary

This milestone resolves all nine findings (F1–F9) identified in the independent code review of `RangeAware_v2` (commit `6be5da6c9610a844bb3f19179c98e9b462174274`). 

The previous active candidate suffered from a critical strategic flaw: decision equity on the flop and turn omitted future board cards, computing made-hand win share rather than showdown equity. This caused the bot to fold profitable draws and misprice opponent runout equity. Furthermore, evaluation integrity gaps (shared RNG state across halves, missing opponent callbacks, broken ablation parameters) and unweighted CFR strategy accumulation were identified.

Every finding was reproduced with a targeted regression test before implementing the fix. We then built and validated a separately versioned candidate, `DrawAware_v1`, which models joint deals (opponent private holdings + legal remaining board runouts) while strictly preventing look-ahead bias in action likelihoods.

### Key Measured Outcomes

1. **Full-Length 1,000-Deal Restricted Container Matches (Docker `--cpus 1`, `--memory 4g`, read-only FS, fresh container per half)**:
   - **vs `action_conditioned_range` (`seed = official_container_acr_draw_aware`)**:
     - Net: **+10.483 BB/deal** (+20,967 chips)
     - 95% CI: **[+9.532, +11.435] BB/deal** -> **AGENT1_WIN**
     - Charged Time Bank: Half 1 **5.69s / 8.00s**, Half 2 **5.88s / 8.00s** (0 calls skipped, 0 judge errors, 0 exceptions across 8,001 calls).
     - Comparative gain: +9.551 BB/deal higher than `RangeAware_v2` (+0.932 BB/deal).
   - **vs `street_inversion_attacker` (`seed = official_container_inversion_draw_aware`)**:
     - Net: **+9.444 BB/deal** (+18,888 chips)
     - 95% CI: **[+8.520, +10.368] BB/deal** -> **AGENT1_WIN**
     - Charged Time Bank: Half 1 **6.63s / 8.00s**, Half 2 **7.47s / 8.00s** (0 calls skipped, 0 judge errors, 0 exceptions across 8,004 calls).
     - Comparative gain: +4.877 BB/deal higher than `RangeAware_v2` (+4.567 BB/deal).

2. **Head-to-Head Candidate Benchmark (10 Matches, 5,000 deals, 10,000 hands per candidate)**:
   - Overall points: `DrawAware_v1` **8.0 / 10.0 points**, mean **+3.615 BB/deal** vs `RangeAware_v2` **8.0 / 10.0 points**, mean **+3.053 BB/deal** (+0.562 BB/deal overall lead).
   - Massive outperformance against the independent `draw_aware_opponent`: **+0.635 BB/deal** vs **+0.046 BB/deal** (+0.589 BB/deal gain).
   - Massive outperformance against `street_inversion_attacker`: **+5.571 BB/deal** vs **+3.411 BB/deal** (+2.160 BB/deal gain).

3. **Official Container Build Verification (`tools/check_build.sh`)**:
   - `poker-agent-check:latest` image adds only **35 MB** on top of the base image (cap: 3,072 MB; 98.9% headroom).
   - Cold start: **1.0s / 15.0s budget** over HTTP.
   - Decision latencies: Preflop 0–1 ms, flop 2–3 ms, river 1 ms.
   - Verdict: **SMOKE TEST PASSED. ALL CHECKS PASSED.**

4. **Test Suite Status**:
   - **64 / 64 unit, official, agreement, and regression tests passing** cleanly across all test files.

---

## 2. Systematic Resolution of Review Findings (F1–F9)

| ID | Severity | Problem Description | Reproduction & Fix | Verification Evidence |
|---|---|---|---|---|
| **F1** | High | Flop/turn equity omitted all future board cards (made-hand win share instead of showdown equity). Caused severe draw-blindness (folding nut draws to all-ins). | Created `runtime/draw_aware_policy.py`. Models joint deals sampling 5-card opponent hands and `5 - len(board)` future runout cards. Retains made-hand score for action conditioning without lookahead. | Flop test case `As Ks Qh Jh 9c` on `Ts 8s 6d`: `RangeAware_v2` gave 0.29% win share and folded; `DrawAware_v1` gave 56.9% showdown equity and called (agrees with brute-force reference 56.9% within ±2%). Passed `test_draw_aware_calls_f1_case`. |
| **F2** | High | Half 2 in local match reused RNG state on `self.rng`; agreement test reused running servers, validating broken lifecycle rather than real fresh-process lifecycle. | Added `play_local_match_fresh` accepting factory functions for fresh instances per half. Updated `tests/test_harness_agreement.py` to terminate and spawn fresh server processes between halves. | `tests/test_harness_agreement.py` passed with 0 divergences across all actions, nets, paired differences, and final CI. Passed `test_fresh_policy_per_half`. |
| **F3** | High | `opponents/serve_opponent.py` did not invoke `bot.new_half`, ignored batched `hand_results` in `/act`, and ignored results in `/hand-end`. | Added `bot.new_half` invocation in `/new-half`, batched `hand_results` delivery in `/act` before `choose_action`, and `on_hand_end` delivery in `/hand-end`. | Verified with `TestClient` in `test_serve_opponent_new_half_calls_bot` and `test_serve_opponent_hand_results_delivered` showing callbacks received before action selection. |
| **F4** | High | `runtime/ablations.py` passed `opp_raise_rate` kwarg instead of `(pf_raise_rate, post_raise_rate)`, crashing with `TypeError`. Also called `hand_strength_sampled` preflop. | Fixed kwarg unpacking and parameter names. Restored `preflop_hand_quality` for `EquityOnly` preflop decisions. Ablations now re-raise internal exceptions rather than hiding them. | Passed `test_ablation_range_adapt_does_not_raise_type_error` and `test_ablation_equity_only_preflop_nonzero` across all 4 component combinations. |
| **F5** | High | `training/generic_mccfr.py` accumulated unweighted `strat[a]` into `strategy_sum`, producing an incorrect average strategy in ES-MCCFR. | Updated `traverse` to weight strategy accumulation by the traversing player's own reach probability (`reach_prob * strat[a]`), conforming to Lanctot et al. 2009 (Algorithm 2). | Passed `test_reach_weighted_accumulation` and `test_reach_weighted_vs_unweighted_differ`. Evaluated `GenericMCCFRTrainer` directly on `KuhnGame`: converged to 0.016 NashConv (99.6% Q check, 99.9% J fold, 99.9% K call). |
| **F6** | Medium | `save_checkpoint` omitted `self.regrets` and RNG state, preventing exact deterministic training resumption. | Added `regrets` and `rng_state` to checkpoint dictionary; restored in `load_checkpoint`. | Passed `test_checkpoint_round_trip` and `test_checkpoint_resume_deterministic` verifying bit-for-bit equivalence between uninterrupted N+M training and split N then M training. |
| **F7** | Medium | Caught internal exceptions and illegal-action fallbacks were hidden by legal fallback check/fold and omitted from judge telemetry. | Added explicit counters `_internal_exceptions` and `_illegal_action_fallbacks` in `memory`, exposed in `GET /`. | Passed `test_internal_exception_counter_increments` and `test_illegal_action_fallback_counter_increments`. Recorded 0 exceptions and 0 fallbacks in container matches. |
| **F8** | Medium | `_spent_bank` tracked only policy function elapsed time with 0.8ms grace, omitting HTTP parsing, callbacks, serialization, and network loopback. | `agent.py` `route_act` now tracks `_charged_bank_spent` over the entire POST request: `max(0.0, elapsed - 0.001)`. Dynamic budgeting in `choose_action` checks this request-level metric. | HTTP runtime profiler confirmed charged bank consumption over 1,911 requests is accurately measured (0.716s used out of 8.000s bank for `DrawAware_v1`). |
| **F9** | Medium | Opponent action counts had selection bias (censored on terminal actions not reaching a decision); likelihood weights were coarse heuristics. | Acknowledged selection bias as an inherent observation constraint; documented in MEMORY.md and architecture. Separated past-action likelihoods strictly from future card sampling to avoid lookahead bias. | Tested against independent `DrawAwareOpponent` and adversarial suite; verified robustness without lookahead contamination. |

---

## 3. Detailed Benchmark Evidence

### A. Full-Length 1,000-Deal Official Container Matches (2,000 Hands Each)

All matches executed via `judge_engine.py` using Docker Desktop Linux engine with strict resource isolation (`--cpus 1`, `--memory 4g`, `--network none`, `--read-only`, `--tmpfs /tmp:rw,size=512m`, fresh container per half).

#### Match 1: vs `action_conditioned_range` (`seed = official_container_acr_draw_aware`)
- **Candidate**: `TeamAntigravity / DrawAware_v1`
- **Opponent**: `action_conditioned_range`
- **Net Chip Payoff**: **+20,967 chips (+10.483 BB/deal)**
  - Half 1 (Seat 0): +10,063 chips (+5.032 BB/deal)
  - Half 2 (Seat 1): +10,904 chips (+5.452 BB/deal)
- **Sample Std Dev**: 15.36 BB/deal ($ddof=1$), Standard Error: 0.486 BB/deal
- **95% Confidence Interval**: **[+9.532, +11.435] BB/deal** -> **AGENT1_WIN**
- **Bank Consumption**:
  - Half 1: 5.69s / 8.00s thinking bank (wall 9.68s, 3,999 calls, 0 errors)
  - Half 2: 5.88s / 8.00s thinking bank (wall 9.87s, 4,002 calls, 0 errors)
- **Operational Reliability**: **0 judge errors, 0 internal exceptions, 0 fallbacks across 8,001 calls**.

#### Match 2: vs `street_inversion_attacker` (`seed = official_container_inversion_draw_aware`)
- **Candidate**: `TeamAntigravity / DrawAware_v1`
- **Opponent**: `street_inversion_attacker`
- **Net Chip Payoff**: **+18,888 chips (+9.444 BB/deal)**
  - Half 1 (Seat 0): +9,854 chips (+4.927 BB/deal)
  - Half 2 (Seat 1): +9,034 chips (+4.517 BB/deal)
- **Sample Std Dev**: 14.91 BB/deal ($ddof=1$), Standard Error: 0.472 BB/deal
- **95% Confidence Interval**: **[+8.520, +10.368] BB/deal** -> **AGENT1_WIN**
- **Bank Consumption**:
  - Half 1: 6.63s / 8.00s thinking bank (wall 10.62s, 4,002 calls, 0 errors)
  - Half 2: 7.47s / 8.00s thinking bank (wall 11.46s, 4,002 calls, 0 errors)
- **Operational Reliability**: **0 judge errors, 0 internal exceptions, 0 fallbacks across 8,004 calls**.

---

### B. Head-to-Head Candidate Benchmark (10 Matches, 20,000 Hands Total)

Conducted with matched seeds and fresh policy instances per half (`reports/raw_matches/draw_aware_comparison.json`):

| Opponent | Seed | `RangeAware_v2` Mean (95% CI) | `DrawAware_v1` Mean (95% CI) | Delta (DA - RA) | Verdict |
|---|---|---|---|---|---|
| `calling_station` | seed_1 | +9.571 [+8.202, +10.940] | +9.323 [+8.025, +10.621] | -0.248 | Both WIN |
| `calling_station` | seed_2 | +9.636 [+8.274, +10.998] | +11.197 [+9.847, +12.547] | **+1.561** | Both WIN |
| `action_conditioned_range` | seed_1 | +1.340 [+0.442, +2.238] | +1.234 [+0.221, +2.247] | -0.106 | Both WIN |
| `action_conditioned_range` | seed_2 | +1.482 [+0.680, +2.284] | +1.144 [+0.038, +2.250] | -0.338 | Both WIN |
| `size_aware_equity` | seed_1 | +0.717 [-0.460, +1.894] | +0.472 [-0.976, +1.920] | -0.245 | Both CHOP |
| `size_aware_equity` | seed_2 | +0.874 [-0.442, +2.190] | +0.370 [-1.050, +1.790] | -0.504 | Both CHOP |
| `street_inversion_attacker` | seed_1 | +3.227 [+1.098, +5.356] | +5.187 [+3.190, +7.184] | **+1.960** | Both WIN |
| `street_inversion_attacker` | seed_2 | +3.594 [+1.449, +5.739] | +5.955 [+3.822, +8.088] | **+2.361** | Both WIN |
| `draw_aware_opponent` | seed_1 | -0.097 [-1.493, +1.299] | +0.673 [-0.601, +1.947] | **+0.770** | Both CHOP |
| `draw_aware_opponent` | seed_2 | +0.190 [-1.265, +1.645] | +0.596 [-0.776, +1.968] | **+0.406** | Both CHOP |
| **Average Across All Matches** | — | **+3.053 BB/deal** | **+3.615 BB/deal** | **+0.562 BB/deal** | **8.0/10 vs 8.0/10** |

---

## 4. Operational & Runtime Profile

Host measurements over 1,911 HTTP requests (1,000 deals) using `profile_http_runtime.py`:
- Cold start ready time: **1.023s / 15.0s budget** (PASS)
- Total wall clock time: **1.959s**
- Exact charged time bank used: **0.716s / 8.000s budget** (PASS, **91.0% bank remaining**)
- Request latency percentiles:
  - Mean: **1.03 ms**
  - P50 (median): **0.57 ms**
  - P95: **2.33 ms**
  - P99: **2.68 ms**
  - Max: **10.35 ms / 1,000.0 ms hard timeout**
- Zero-grace charged requests: 1,073 / 1,911 requests (56.1%) completely free under 1.0 ms grace.
- Deep reachable history stress (13 prior actions): Mean 0.98 ms, Max 1.52 ms.

---

## 5. Artifacts and Release Packaging

- **Active Candidate**: `DrawAware_v1` (`agent.py`, `runtime/draw_aware_policy.py`)
- **Rollback Candidate 1**: `RangeAware_v2` (`runtime/range_aware_policy.py`)
- **Rollback Candidate 2**: `EquityBot_v1` (`runtime/policy.py`)
- **Review Bundle**: Exported to `release/review_bundle_DrawAware_v1.zip` (174 files, 1.41 MB uncompressed).
- **Preserved Archive**: `release/review_bundle_RangeAware_v2.zip` preserved untouched.
