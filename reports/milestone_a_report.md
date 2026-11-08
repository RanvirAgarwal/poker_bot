# Milestone A Experiment Report: Baseline Implementation & Evaluation

## Executive Summary
This report documents the implementation, correctness verification, and empirical benchmarking of our heads-up Short Deck PLO5 poker bot (`EquityBot_v1`) for the TAMU Datathon tournament.

- **Candidate ID**: `EquityBot_v1`
- **Source Revision**: Commit `2d703a1`
- **Result**: Undefeated across all 5 registered baseline opponents in duplicate screening (5/5 wins); Official judge match win (+14.30 BB/deal vs CallingStation, 1.0 - 0.0 match points); 0 operational errors.
- **Timing Margin**: Startup latency 0.134s (limit 15s); Thinking time bank usage 0.06s / 8.00s (<1% used); Decision latency 1 - 17ms (limit 1,000ms).

---

## 1. Verified Specification & Rule Mechanics
We validated our system against the official tournament referee (`starter/evaluator.py`, `starter/game.py`, `starter/judge_engine.py` at commit `c83ab6e`):
- **36-card deck**: Ranks 6 to Ace in 4 suits.
- **Short Deck ranking modifications**:
  - Flush > Full House (flushes rarer due to shortened deck).
  - Three of a Kind > Straight (straights more frequent).
  - Wheel straight: A-6-7-8-9 (lowest straight, nine-high).
- **Omaha 2+3 Rule**: Exactly 2 of 5 hole cards combined with exactly 3 of 5 board cards.
- **Raise caps & sizing**: Maximum 4 voluntary raises per street; pot-limit and half-pot bounds strictly enforced.
- **Duplicate format**: 1,000 deals per half (2,000 total hands) with seat swapping in half 2 to cancel card luck.

---

## 2. Test Suite Verification
All unit and regression suites pass with 100% success rate:
- **`tests/test_rules.py`**: 19 tests covering rankings, Omaha selection, state transitions, raise caps, and dealing determinism -> **19/19 PASSED (0.24s)**.
- **`tests/test_agent_protocol.py`**: 5 tests covering health checks, token authentication, `/new-half` resets, legal action validation, and error safety -> **5/5 PASSED (0.43s)**.
- **`starter/test_agent.py`**: 12 official starter tests -> **12/12 PASSED (1.48s)**.
- **`starter/tools/smoke_test.py`**: Official tournament container smoke test -> **SMOKE TEST PASSED (0 errors, 1-17ms response)**.

---

## 3. Empirical Benchmarks (Duplicate Matches)

### A. Local Screening Suite (100 Duplicate Deals = 200 Hands Each)
*Measured using exact sample standard deviation (ddof=1) and 95% confidence intervals matching `judge_engine.py`.*

| Opponent | Family / Behavior | Verdict | Mean BB / deal | 95% Confidence Interval | Speed (hands/s) | Errors |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| `check_fold` | Passive Starter Baseline | **AGENT1_WIN** | **+1.360** | [+1.26, +1.46] | 4,828 | 0 |
| `calling_station` | Inelastic Calling Station | **AGENT1_WIN** | **+11.210** | [+8.36, +14.06] | 467 | 0 |
| `random` | Stochastic Noise | **AGENT1_WIN** | **+7.060** | [+2.08, +12.04] | 1,455 | 0 |
| `always_raise` | Hyper-Aggressive Sizing | **AGENT1_WIN** | **+8.590** | [+4.65, +12.53] | 1,634 | 0 |
| `equity_call` | Equity / Pot Odds Bot | **AGENT1_WIN** | **+2.900** | [+1.13, +4.67] | 397 | 0 |

### B. Official `judge_engine.py` HTTP Match (50 Duplicate Deals = 100 Hands)
- **Opponent**: `Challenges Team / CallingStation` (port 5009)
- **Agent 1**: `TeamAntigravity / EquityBot_v1` (port 5008)
- **Net Chips**: Half 1 (+964 chips), Half 2 (+466 chips) -> **Total: +1,430 chips (+14.300 BB/deal)**
- **Confidence Interval (z=1.96)**: **[+10.193, +18.407] BB/deal** (entirely above 0)
- **Judge Verdict**: **`RESULT: AGENT1_WIN`** (Points: 1.0 - 0.0)
- **Resource Usage**: Thinking time charged: 0.06s of 8.00s bank (<1% of budget); 0 errors; wall clock speed 179 hands/s.

---

## 4. CFR Exploration & Ablation
We implemented an External-Sampling Monte Carlo Counterfactual Regret Minimization (ES-MCCFR) pipeline in `training/`:
- **Discovered InfoSets**: 48,421 information sets in 2,000 iterations (14.3s training time, 140 it/s).
- **Ablation Comparison**:
  - `CFRBot_v1` (2k iterations) achieved 3 wins / 2 chops vs `EquityBot_v1`'s 5 wins / 0 chops.
  - Reason: 2,000 iterations is insufficient for 48,000+ infosets (~1-2 visits per node); regrets have not yet converged.
- **Decision**: Keep `EquityBot_v1` as the active tournament candidate in `agent.py` based on empirical evidence, while continuing CFR training scaling offline.

