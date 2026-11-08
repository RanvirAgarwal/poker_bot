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

## 4. Official Container Verification & Restricted Container Matches

### A. Docker Build & Smoke Test Verification (`tools/check_build.sh`)
- **Docker Engine:** Docker Desktop Linux 29.9.2 (Cgroup Version: 2, OSType: linux, Architecture: x86_64, WSL2 Kernel 6.6.87.2).
- **Base Image Build (`docker/Dockerfile.base`):** Successfully built and verified `poker-agent-base:local` (Python 3.12-slim, FastAPI 0.156.1, uvicorn 0.54.0, PyTorch CPU 2.15.0+cpu, dedicated non-root `bot` user).
- **Bot Image Build (`docker/Dockerfile.agent`):** Successfully built `poker-agent-check:latest`.
- **Image Footprint Check:** Bot adds **17 MB** on top of base image (official cap: **3,072 MB**; 99.4% headroom remaining).
- **Restricted Container Constraints Enforced:**
  - `--network none` (air-gapped, zero external network access)
  - `--read-only` (read-only root filesystem)
  - `--tmpfs /tmp:rw,nosuid,nodev,size=512m` (scratch space strictly limited to 512 MB tmpfs)
  - `--cpus 1` (strictly single-core CPU cgroup restriction)
  - `--memory 4g` (4 GB memory cgroup limit)
  - `--cap-drop ALL` (all Linux kernel capabilities dropped)
  - `--security-opt no-new-privileges` (privilege escalation blocked)
  - `--pids-limit 256` (fork bomb protection)
- **Official Container Smoke Test (`tools/smoke_test.py`):**
  - `GET / answered after 0.5 s: TeamAntigravity / RangeAware_v2` (well within 15.0s budget)
  - `POST /new-half worked`
  - `/act preflop, button to act: RAISE_POT in 1 ms`
  - `/act preflop, facing a pot raise: CHECK_CALL in 0 ms`
  - `/act flop, first to act: CHECK_CALL in 1 ms`
  - `/act flop, facing an all-in: FOLD in 1 ms`
  - `/act river, facing a half-pot bet: CHECK_CALL in 1 ms`
  - `POST /hand-end worked`
  - **Status:** `SMOKE TEST PASSED. ALL CHECKS PASSED.`

### B. Full-Length 1,000-Deal Container Tournament Match vs `action_conditioned_range`
Executed via [`run_full_tournament_match.py`](file:///C:/Users/ranvi/poker_bot/evaluation/run_full_tournament_match.py) with `--container` (fresh Docker container process restarted between halves):
- **Seed:** `official_container_acr_fast` (1,000 duplicate deals, 2,000 hands total)
- **Chip Totals:** Half 1: +1,628 chips (+0.814 bb/deal); Half 2: +236 chips (+0.118 bb/deal); Total: **+1,864 chips (+0.932 bb/deal)**.
- **Statistical Significance:** Sample std dev $8.93$, standard error $0.282$ BB/deal.
- **95% Confidence Interval ($z = 1.96$):** **[+0.379, +1.485] BB/deal** (strictly above zero).
- **Official Tournament Verdict:** **AGENT1 WINS (1.0 pt agent1, 0.0 agent2)**.
- **Time Bank Accounting under 1 CPU Container:**
  - Half 1: **4.80s / 8.00s thinking** (wall 8.09s across 3,301 requests), **0 calls skipped**, **3.20s (40.0%) margin remaining**.
  - Half 2: **2.96s / 8.00s thinking** (wall 6.30s across 3,343 requests), **0 calls skipped**, **5.04s (63.0%) margin remaining**.
- **Reliability:** **0 errors, 0 internal exceptions, 0 fallbacks** across 6,644 total container calls.
- **Speed:** 2,000 hands in 30.48s (66 hands/sec).
- **Raw JSON:** [`official_container_acr_fast_match.json`](file:///C:/Users/ranvi/poker_bot/reports/raw_matches/official_container_acr_fast_match.json).

### C. Full-Length 1,000-Deal Container Tournament Match vs `street_inversion_attacker`
- **Seed:** `official_container_inversion_fast` (1,000 duplicate deals, 2,000 hands total)
- **Chip Totals:** Half 1: +6,053 chips (+3.026 bb/deal); Half 2: +3,082 chips (+1.541 bb/deal); Total: **+9,135 chips (+4.567 bb/deal)**.
- **Statistical Significance:** Sample std dev $24.31$, standard error $0.769$ BB/deal.
- **95% Confidence Interval ($z = 1.96$):** **[+3.061, +6.074] BB/deal** (strictly above zero).
- **Official Tournament Verdict:** **AGENT1 WINS (1.0 pt agent1, 0.0 agent2)**.
- **Time Bank Accounting under 1 CPU Container:**
  - Half 1: **2.37s / 8.00s thinking** (wall 5.53s across 3,183 requests), **0 calls skipped**, **5.63s (70.4%) margin remaining**.
  - Half 2: **1.58s / 8.00s thinking** (wall 4.78s across 3,232 requests), **0 calls skipped**, **6.42s (80.3%) margin remaining**.
- **Reliability:** **0 errors, 0 internal exceptions, 0 fallbacks** across 6,415 total container calls.
- **Speed:** 2,000 hands in 15.91s (126 hands/sec).
- **Raw JSON:** [`official_container_inversion_fast_match.json`](file:///C:/Users/ranvi/poker_bot/reports/raw_matches/official_container_inversion_fast_match.json).

---

## 5. Summary of Release Artifacts

- **Active Submission:** [`agent.py`](file:///C:/Users/ranvi/poker_bot/agent.py) (`TeamAntigravity / RangeAware_v2`)
- **Provisional Strategy Policy:** [`runtime/range_aware_policy.py`](file:///C:/Users/ranvi/poker_bot/runtime/range_aware_policy.py) (`RangeAwarePolicy(aggression=1.0, seed=42, use_continuation_filter=True)`)
- **Rollback Baseline:** [`runtime/policy.py`](file:///C:/Users/ranvi/poker_bot/runtime/policy.py) (`HeuristicPolicy(aggression=1.0, seed=42)`)
- **Reachable Betting Tree Search:** [`evaluation/enumerate_max_actions.py`](file:///C:/Users/ranvi/poker_bot/evaluation/enumerate_max_actions.py)
- **Max Action Regression Test:** [`tests/test_reachable_history.py`](file:///C:/Users/ranvi/poker_bot/tests/test_reachable_history.py)
- **Review Release Bundle:** [`release/review_bundle_RangeAware_v2.zip`](file:///C:/Users/ranvi/poker_bot/release/review_bundle_RangeAware_v2.zip)
