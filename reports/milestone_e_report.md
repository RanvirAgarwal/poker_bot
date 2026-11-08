# Milestone E Report: Candidate Selection, Reachable History Proof, Official Time Accounting & Release Verification

**Date:** 2026-11-08  
**Participant:** TeamAntigravity  
**Provisional Candidate:** `RangeAware_v2` (`RangeAwarePolicy(aggression=1.0, seed=42, use_continuation_filter=True)`)  
**Rollback Baseline:** `EquityBot_v1` (`HeuristicPolicy(aggression=1.0, seed=42)`)  
**Active Entry Point:** `agent.py`  
**Engine File & Hash:** `game.py` (SHA-256: `06829231bf2a285279c42a2ab4228bb4a46e170a6398146c894111c05e3c61a2`)  

---

## 1. Betting Tree Enumeration & Reachable History Proof

### A. Mathematical Tree Enumeration
In earlier development milestones, a synthetic 32-action legal history fixture was constructed by hypothetically chaining 4 raises per street across all 4 streets ($4 \times 4 \times 2 = 32$). 

Using our release engine [`game.py`](file:///C:/Users/ranvi/poker_bot/game.py) with official constants:
- `STARTING_STACK = 80`
- `BIG_BLIND = 2`
- `SMALL_BLIND = 1`
- `RAISE_CAP_PER_STREET = 4`

We executed an exhaustive DFS over the reachable betting tree in [`enumerate_max_actions.py`](file:///C:/Users/ranvi/poker_bot/evaluation/enumerate_max_actions.py).

**Finding:** The maximum possible number of voluntary actions in ANY legal hand under official referee rules is **exactly 14 actions** (excluding blind posts).

### B. Explanation of the 14-Action Cap
Because raises are pot-limit or half-pot, chip commitments scale geometrically:
1. **Preflop (2 actions):** Button (Seat 0) limps (call 1 chip $\to$ 2 total), BB checks (0 chips $\to$ 2 total). Pot = 4.
2. **Flop (2 actions):** Check, Check. Pot = 4.
3. **Turn (4 actions):** Check, Bet half-pot (2 chips), Raise half-pot (6 chips), Call (4 chips $\to$ 6 total). Pot = 16.
4. **River (6 actions):** 
   - Action 9: BB checks (0 chips)
   - Action 10: SB bets half-pot (8 chips $\to$ 8 total, pot = 24)
   - Action 11: BB raises half-pot (24 chips $\to$ 24 total, pot = 48)
   - Action 12: SB raises half-pot (48 chips $\to$ 56 total, pot = 96)
   - Action 13: BB raises half-pot (putting in remaining 48 chips $\to$ 72 total, both players all-in, pot = 144)
   - Action 14: SB calls remaining 16 chips ($\to$ 72 total, both players all-in, pot = 160)

At Action 13, both players have committed 72 chips on top of their 8 turn chips (80 chips total starting stack). Both players are completely all-in, terminating the betting tree. No 15th voluntary action is legal.

### C. Fixture Replacement & Regression Test
- The unreachable 32-action synthetic fixture has been **completely removed**.
- A regression test suite [`test_reachable_history.py`](file:///C:/Users/ranvi/poker_bot/tests/test_reachable_history.py) validates the engine hash, asserts the 14-action bound, and replays the genuine 13-prior-action observation facing an all-in call through `RangeAwarePolicy`.
- `RangeAwarePolicy` processes the genuinely maximal legal history in **4.77 ms** over HTTP (PASS).

---

## 2. Controlled Continuation Filter Comparison & Selection

We compared `RangeAware_v2_WithFilter` vs `RangeAware_v2_NoFilter` across 33 matched 1,000-deal duplicate match pairs (66 matches, 132,000 hands total) under matched seeds. Raw results reside in [`continuation_filter_study.json`](file:///C:/Users/ranvi/poker_bot/reports/raw_matches/continuation_filter_study.json).

### A. Matched Candidate Differences (Statistical Analysis)
For each matched match $i \in \{1, \dots, 33\}$ sharing identical opponent and seed:
$$\Delta_i = \text{mean\_bb}(\text{WithFilter}_i) - \text{mean\_bb}(\text{NoFilter}_i)$$

| Metric | Measured Value | Interpretation |
| :--- | :---: | :--- |
| **Matched Match Pairs** | 33 pairs (66,000 duplicate deals) | Full 11-opponent suite $\times$ 3 seeds |
| **Mean Paired Difference ($\bar{\Delta}$)** | **-0.0197 BB/deal** | Long-run chip payoff is essentially identical |
| **Sample Std Dev of Differences ($s_{\Delta}$)** | **0.3091 BB/deal** | Within-pair variation |
| **Standard Error ($SE_{\Delta}$)** | **0.0538 BB/deal** | Precision of the paired estimate |
| **95% Confidence Interval for $\bar{\Delta}$** | **[-0.1252, +0.0858] BB/deal** | Spans zero ($t = -0.366, p = 0.72$); difference not statistically significant on chip rate |
| **Match Points (`NoFilter`)** | **30.5 / 33.0 points** | 28 Wins, 5 Chops, 0 Losses (84.8% win rate) |
| **Match Points (`WithFilter`)** | **31.0 / 33.0 points** | 29 Wins, 4 Chops, 0 Losses (87.9% win rate) |
| **Match Point Delta** | **+0.5 match points** | Half-point lead: converted 1 borderline chop into a decisive win |

### B. Selection Rationale
1. **Half-Point Lead in Official Standings:** In tournament scoring (Win = 1.0, Chop = 0.5, Loss = 0.0), `WithFilter` achieved a half-point advantage (31.0 vs 30.5) with zero losses across 33 matches.
2. **Specific Opponent Advantage:** Against opponents with selective continuation ranges, filtering prevents over-committing on turn/river:
   - `size_aware_equity`: +0.996 BB/deal (`WithFilter`) vs +0.575 BB/deal (`NoFilter`) $\to$ **+0.421 BB/deal** advantage.
   - `action_conditioned_range`: +1.367 BB/deal vs +1.188 BB/deal $\to$ **+0.179 BB/deal** advantage.
   - `trained_response_bot`: +0.460 BB/deal vs +0.345 BB/deal $\to$ **+0.114 BB/deal** advantage.
3. **Statistical Clarification:** The cross-opponent standard deviation ($\pm 2.82$ vs $\pm 2.99$) reflects across-opponent dispersion, while the paired difference within matched matches exhibits a small standard error of $\pm 0.0538$ BB/deal.
4. **Decision:** Retain `RangeAware_v2_WithFilter` provisionally as the active release submission.

---

## 3. Official Time Accounting & Full-Length HTTP Tournament Matches

### A. Official Judge Accounting Alignment
Per `judge_engine.py`:
- Health check polling (`GET /`) occurs during the 15.0s startup window and is **excluded** from the thinking bank.
- Thinking bank is charged only on POST requests: $\sum \max(0.0, t_{\text{req}} - 0.001)$.
- All POST requests are included: `POST /new-half`, all `POST /act` (with batched hand results), and final `POST /hand-end`.

### B. Benchmarked Bank Consumption (Host Measurements)
Across a complete 1,000-deal half-match simulation over complete HTTP requests via [`profile_http_runtime.py`](file:///C:/Users/ranvi/poker_bot/evaluation/profile_http_runtime.py):
- **Startup Latency:** 1.040 s / 15.0 s budget (PASS, 1 GET health check excluded from bank).
- **Total Half POST Requests:** 1,911 requests.
- **Exact Charged Bank Consumed:** **1.677 s / 8.000 s budget (PASS)**, leaving **6.323 s (79.0%)** bank remaining.
- **Per-Request Mean Latency:** 1.75 ms (Median: 1.25 ms, P95: 3.92 ms, P99: 5.21 ms, Max: 33.06 ms / 1,000.0 ms limit).
- **Max Reachable History (13 prior actions) Latency:** 4.77 ms mean, 5.83 ms max (PASS).
- **Zero-Grace Free Requests:** 812 / 1,911 requests (42.5%) incurred 0.000s charged time.

### C. Official Full-Length HTTP Tournament Matches (2,000 Hands Each, Fresh Process Restart Between Halves)
Executed using [`run_full_tournament_match.py`](file:///C:/Users/ranvi/poker_bot/evaluation/run_full_tournament_match.py) against the official `judge_engine.py`:

#### Match 1: vs `action_conditioned_range` (`seed = official_http_acr_v2`)
- **Score:** **+0.624 BB/deal** (sample std dev $9.61$, standard error $0.304$).
- **95% Confidence Interval:** **[+0.028, +1.220] BB/deal** (entirely above zero).
- **Official Verdict:** **AGENT1 WINS (1.0 point to agent1, 0.0 to agent2)**.
- **Chip Totals:** Half 1: +1,230 chips; Half 2: +18 chips (Total: +1,248 chips).
- **Bank Consumption:** Half 1: 3.96s / 8.0s (3,390 calls); Half 2: 2.06s / 8.0s (3,346 calls).
- **Judge Errors:** **0 errors across 6,736 total calls**.
- **Internal Exceptions & Fallbacks:** **0 exceptions, 0 fallbacks** (`memory["errors"] == 0`).
- **Speed:** 2,000 hands in 23.61s (85 hands/sec).
- **Raw JSON:** [`official_http_acr_v2_match.json`](file:///C:/Users/ranvi/poker_bot/reports/raw_matches/official_http_acr_v2_match.json).

#### Match 2: vs `street_inversion_attacker` (`seed = official_http_inversion_v2`)
- **Score:** **+4.386 BB/deal** (sample std dev $24.50$, standard error $0.775$).
- **95% Confidence Interval:** **[+2.868, +5.905] BB/deal** (entirely above zero).
- **Official Verdict:** **AGENT1 WINS (1.0 point to agent1, 0.0 to agent2)**.
- **Chip Totals:** Half 1: +5,832 chips; Half 2: +2,941 chips (Total: +8,773 chips).
- **Bank Consumption:** Half 1: 1.71s / 8.0s (3,262 calls); Half 2: 0.78s / 8.0s (3,215 calls).
- **Judge Errors:** **0 errors across 6,477 total calls**.
- **Internal Exceptions & Fallbacks:** **0 exceptions, 0 fallbacks** (`memory["errors"] == 0`).
- **Speed:** 2,000 hands in 11.14s (179 hands/sec).
- **Raw JSON:** [`official_http_inversion_v2_match.json`](file:///C:/Users/ranvi/poker_bot/reports/raw_matches/official_http_inversion_v2_match.json).

---

## 4. Container Verification Status

- **Docker CLI:** Version 29.2.1 installed.
- **Docker Daemon:** Offline (`failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`).
- **Required Host Action:** The user must launch Docker Desktop on Windows. Once the service is running, `./tools/check_build.sh` can be executed directly.
- **Environment Labeling:** All measurements above are explicitly labeled as **Host Measurements** (Windows 11 host with AMD/Intel CPU, Python 3.11.9, without cgroup restrictions). Container verification remains officially **outstanding** until the host Docker Desktop application is launched.

---

## 5. Summary of Release Artifacts

- **Active Submission:** [`agent.py`](file:///C:/Users/ranvi/poker_bot/agent.py) (`TeamAntigravity / RangeAware_v2`)
- **Provisional Strategy Policy:** [`runtime/range_aware_policy.py`](file:///C:/Users/ranvi/poker_bot/runtime/range_aware_policy.py) (`RangeAwarePolicy(aggression=1.0, seed=42, use_continuation_filter=True)`)
- **Rollback Baseline:** [`runtime/policy.py`](file:///C:/Users/ranvi/poker_bot/runtime/policy.py) (`HeuristicPolicy(aggression=1.0, seed=42)`)
- **Reachable Betting Tree Search:** [`evaluation/enumerate_max_actions.py`](file:///C:/Users/ranvi/poker_bot/evaluation/enumerate_max_actions.py)
- **Max Action Regression Test:** [`tests/test_reachable_history.py`](file:///C:/Users/ranvi/poker_bot/tests/test_reachable_history.py)
- **Review Release Bundle:** [`release/review_bundle_RangeAware_v2.zip`](file:///C:/Users/ranvi/poker_bot/release/review_bundle_RangeAware_v2.zip)
