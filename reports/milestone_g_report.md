# Milestone G Report: Qualification, Review Corrections, and Release Verification of Counterplay_v3

**Date**: November 8, 2026  
**Candidate Identifier**: `Counterplay_v3`  
**Entry Point**: `agent.py` (`TeamAntigravity / Counterplay_v3`)  
**Docker Image ID**: `sha256:8e0a567aff158c9e23eeba15d5f5a024878ba3b9b338c31f1209ce705ba51340` (Current local Docker image ID; previous builds `sha256:05ce740f89930fb4ac8800b40f4dc8b065dfb526a349bdd78745d858afd5dcb1`, `sha256:014fa99812add00e1bcb3c7a8144139fcf7b647f950c505f56249b5569a57a84`)  
**Git Branch**: `counterplay-v3-integration`  
**Release Commit SHA**: `5c6adbd96311bae48a7f17fcd2c5f7a92c460282`  
**Rollback Version**: `DrawAware_v1` (commit `a1debba524ce439fcacaec8ff45509140234a15b`, preserved in `release/review_bundle_DrawAware_v1.zip` and `opponents/agent_drawaware_v1.py`)  

---

## 1. Executive Summary

This milestone completes the integration, verification, and official Docker container qualification of `Counterplay_v3`, evaluates the challenger candidate `RobustPortfolio_v4`, and closes all reporting and verification gaps.

The candidate was integrated onto a dedicated `counterplay-v3-integration` branch. All runtime and asset SHA-256 hashes were verified bit-for-bit against `PROVENANCE.json`. Correctness was verified through 16 package tests, all 68 project unit/integration tests, and the official container smoke test suite (`tools/check_build.sh`).

Container qualification was conducted under exact tournament constraints: 1 CPU, 4 GB RAM, read-only root filesystem, 512MB tmpfs, dropped capabilities (`--cap-drop ALL`, `--security-opt no-new-privileges`), and fresh container lifecycles between halves.

Across 9 full 1,000-deal official duplicate tournament matches (18,000 container hands) on three new predeclared seeds against pinned external opponents (Timecasters, TwoStack, and vsmBOT), `Counterplay_v3` achieved **8.5 / 9.0 match points (94.4%)** with an average win rate of **+1.442 BB/deal** and zero operational faults. 

When benchmarked against the preserved `DrawAware_v1` rollback baseline under strictly matched seeds and cards, `Counterplay_v3` demonstrated a **+3.014 BB/deal paired advantage** across all 9 matches, reversing 6 of 6 match losses suffered by `DrawAware_v1` against Timecasters and TwoStack into 5 wins and 1 chop.

Furthermore, across 4 broader baseline styles (`check_fold`, `calling_station`, `random`, `always_raise`), `Counterplay_v3` scored **4.0 / 4.0 points (100%)** at **+6.696 BB/deal mean**.

The challenger candidate `RobustPortfolio_v4` was subjected to container qualification under the same limits, but **exhausted its 8.0-second time bank in every measured half** (3,728 skipped calls vs calling station; 1,488 skipped calls vs r1_6), resulting in outright match defeat to `r1_6` (-0.571 BB/deal). It failed the $\le 6.0$-second promotion headroom policy. Consequently, `Counterplay_v3` is finalized as the selected release.

---

## 2. Asset Integrity & Provenance Verification

All 6 integrated components matched their cryptographic hashes in `PROVENANCE.json` bit-for-bit:

| Component | Destination Path | Size | SHA-256 Hash | Status |
|---|---|---|---|---|
| Entry Point | `agent.py` | 4,243 B | `e54abd0bd10466469b1c895142d366934786837113810efed9f912afc787e93f` | MATCH |
| Dense Equity Engine | `runtime/dense_equity.py` | 1,970 B | `b1bf83bb2b6b8553e97c6a32853205befdaeb4188074737843bfb94f2ff62108` | MATCH |
| Strategy Policy | `runtime/counterplay_policy.py` | 9,307 B | `f92d15d91be9673a7b1275f1a151e60c7b354fce8d1eb28786c32e203da29c23` | MATCH |
| Hyperparameters | `data/policy_config.json` | 647 B | `ca96be32ff47f2cf67e234c5fde71e4114bb87edffd3802cb2a7c526149b3a22` | MATCH |
| Preflop Table | `data/preflop.npy` | 4,524,032 B | `147906e53cfdeab83d325eed31cea56a910b0fbda5419bfffca22708da2a8b84` | MATCH |
| Pair-Triple Table | `data/pair_triple.npy` | 17,992,928 B | `130f83e933db588f47faa10a6b7a4d62e0770e4796c3881233a1418873c10be8` | MATCH |

The policy hyperparameters in `data/policy_config.json` remained strictly frozen throughout qualification.

---

## 3. Official Docker Qualification Results

**Match Protocol**:
- 1,000 duplicate deals per match (2,000 hands total; 1,000 hands per half).
- Seat swap at deal 1,000.
- Fresh container process per half with zero shared state or network access.
- Container limits: `--cpus 1`, `--memory 4g`, `--read-only`, `--tmpfs /tmp:rw,size=512m`, `--cap-drop ALL`, `--security-opt no-new-privileges`.
- Pinned external opponents:
  - **Timecasters**: commit `a61a1388f24c6495695d40be5026479266afb818`
  - **TwoStack**: commit `8f4fbc964c0d2814c36cd3455f25a379e0cf6f66`
  - **vsmBOT**: commit `22330246ecb2143b9256204b106473bdfdeaa7a1`

### Summary Table: Counterplay_v3 Container Matches (18,000 Hands)

| Opponent | Seed | Verdict | Points | Payoff (BB/deal) | 95% Confidence Interval | H1 Bank (8s) | H2 Bank (8s) | Match Elapsed | Errors / Exc / Fallbacks |
|---|---|---|---|---|---|---|---|---|---|
| **Timecasters** | `docker_val_20261108_01` | **CHOP** | 0.5 | +0.669 | [-0.125, +1.462]* | 3.821s | 3.406s | 22.758s | 0 / 0 / 0 |
| **Timecasters** | `docker_val_20261108_02` | **WIN** | 1.0 | +0.930 | [+0.145, +1.714] | 3.837s | 3.306s | 34.106s | 0 / 0 / 0 |
| **Timecasters** | `docker_val_20261108_03` | **WIN** | 1.0 | +0.977 | [+0.156, +1.798] | 4.631s | 4.138s | 35.812s | 0 / 0 / 0 |
| **TwoStack** | `docker_val_20261108_01` | **WIN** | 1.0 | +1.764 | [+0.952, +2.576] | 4.670s | 3.798s | 36.533s | 0 / 0 / 0 |
| **TwoStack** | `docker_val_20261108_02` | **WIN** | 1.0 | +0.758 | [+0.023, +1.492] | 3.793s | 3.565s | 35.965s | 0 / 0 / 0 |
| **TwoStack** | `docker_val_20261108_03` | **WIN** | 1.0 | +1.311 | [+0.565, +2.057] | 3.554s | 3.600s | 34.768s | 0 / 0 / 0 |
| **vsmBOT** | `docker_val_20261108_01` | **WIN** | 1.0 | +2.444 | [+1.851, +3.036] | 2.761s | 2.583s | 37.220s | 0 / 0 / 0 |
| **vsmBOT** | `docker_val_20261108_02` | **WIN** | 1.0 | +2.160 | [+1.620, +2.699] | 2.558s | 2.560s | 36.616s | 0 / 0 / 0 |
| **vsmBOT** | `docker_val_20261108_03` | **WIN** | 1.0 | +1.974 | [+1.420, +2.527] | 2.592s | 2.527s | 37.025s | 0 / 0 / 0 |
| **TOTALS** | *9 Matches* | **8 W, 1 C, 0 L** | **8.5 / 9.0** | **+1.442** | *8 exclude 0, 1 includes 0* | **Max 4.670s** | **Max 4.138s** | **310.8s total** | **0 / 0 / 0** |

*\*Reporting Gap Note*: Exactly eight public-match confidence intervals exclude zero. The first Timecasters match interval `[-0.125, +1.462]` includes zero, resulting in a legitimate tournament CHOP (0.5 points). Match 1 elapsed time of 22.758 seconds has been recovered from raw record `docker_val_Counterplay_v3_timecasters_docker_val_20261108_01_match.json`.

*\*Opponent Bank Exhaustion Label*: Against vsmBOT, the opponent exhausted its 8.00s time bank in both halves across all three seeds (`A2_bank: 8.00s`, skipping 1,343–1,432 decisions per match). Under tournament rules, an agent with an exhausted bank plays check/fold. While this is an official win under judge accounting, vsmBOT's high payoff (+2.192 BB/deal) partly reflects opponent timing failure rather than purely unexploitable counterplay. Against Timecasters and TwoStack, neither agent emptied its bank (Timecasters bank 1.57–3.81s; TwoStack bank 3.30–3.40s; 0 skipped decisions).

---

## 4. Matched Comparison vs Preserved Rollback (DrawAware_v1)

To isolate strategic improvement from card distribution, `DrawAware_v1` was evaluated on the identical 9 seeds and opponents under the same protocol.

### Paired Delta Table ($\text{Counterplay\_v3} - \text{DrawAware\_v1}$)

| Opponent | Seed | Counterplay_v3 (BB/deal) | DrawAware_v1 (BB/deal) | DrawAware Verdict | Paired $\Delta$ (BB/deal) | Strategic Significance |
|---|---|---|---|---|---|---|
| **Timecasters** | `..._01` | +0.669 | -3.161 | AGENT2_WIN (Loss) | **+3.830** | Loss reversed to Chop |
| **Timecasters** | `..._02` | +0.930 | -4.459 | AGENT2_WIN (Loss) | **+5.388** | Loss reversed to Decisive Win |
| **Timecasters** | `..._03` | +0.977 | -3.042 | AGENT2_WIN (Loss) | **+4.019** | Loss reversed to Decisive Win |
| **TwoStack** | `..._01` | +1.764 | -1.715 | AGENT2_WIN (Loss) | **+3.479** | Loss reversed to Decisive Win |
| **TwoStack** | `..._02` | +0.758 | -3.433 | AGENT2_WIN (Loss) | **+4.190** | Loss reversed to Decisive Win |
| **TwoStack** | `..._03` | +1.311 | -2.176 | AGENT2_WIN (Loss) | **+3.487** | Loss reversed to Decisive Win |
| **vsmBOT** | `..._01` | +2.444 | +1.004 | AGENT1_WIN (Win) | **+1.439** | +143% margin increase |
| **vsmBOT** | `..._02` | +2.160 | +1.216 | AGENT1_WIN (Win) | **+0.944** | +78% margin increase |
| **vsmBOT** | `..._03` | +1.974 | +1.625 | AGENT1_WIN (Win) | **+0.349** | +21% margin increase |
| **OVERALL** | *Mean* | **+1.442** | **-1.571056** | **3.0 / 9.0 pts** | **+3.014** | **+3.014 BB/deal gain** |

*\*Reporting Gap Note*: `DrawAware_v1`'s all-nine mean is **-1.571056 BB/deal**; its Timecasters/TwoStack-only mean across 6 matches is **-2.997417 BB/deal**. `DrawAware_v1` was systematically exploited by Timecasters' adaptive defense and TwoStack's calibrated sizing, losing all 6 matches. `Counterplay_v3` strictly outperformed `DrawAware_v1` across all 9 matched deals.

---

## 5. Broader Styles Evaluation (Container Matches)

`Counterplay_v3` was evaluated against four canonical opponent archetypes (1,000 deals / 2,000 hands each in restricted container):

| Opponent Archetype | Style Profile | Verdict | Points | Payoff (BB/deal) | 95% Confidence Interval | H1 Bank | H2 Bank | Speed |
|---|---|---|---|---|---|---|---|---|
| `check_fold` | Ultra-passive | **AGENT1_WIN** | 1.0 | **+1.475** | [+1.462, +1.487] | 0.387s | 0.482s | 477 hands/s |
| `calling_station` | Inelastic passive | **AGENT1_WIN** | 1.0 | **+11.906** | [+10.838, +12.973] | 4.684s | 4.936s* | 100 hands/s |
| `random` | Uniform noise | **AGENT1_WIN** | 1.0 | **+6.745** | [+5.316, +8.173] | 2.361s | 3.173s | 97 hands/s |
| `always_raise` | Hyper-aggressive | **AGENT1_WIN** | 1.0 | **+6.658** | [+5.007, +8.308] | 3.484s | 2.693s | 111 hands/s |
| **TOTALS** | *4 Styles* | **4 W, 0 L** | **4.0 / 4.0** | **+6.696** | *All positive intervals* | **Max 4.684s** | **Max 4.936s** | *100% wins* |

*\*Reporting Gap Note*: Maximum candidate half-bank use across all thirteen matches (nine public + four baseline) is **4.936340 seconds** (Half 2 vs `calling_station`).

---

## 6. Challenger Qualification Failure (RobustPortfolio_v4)

The challenger candidate `RobustPortfolio_v4` was tested on branch `robust-portfolio-v4-qualification` under the exact same container constraints (1 CPU, 4 GB RAM, read-only root FS, 512MB tmpfs, dropped capabilities, fresh container per half):

| Opponent | Seed | Verdict | Payoff (BB/deal) | 95% Confidence Interval | H1 Bank (8s) | H2 Bank (8s) | Operational Failure |
|---|---|---|---|---|---|---|---|
| `calling_station` | `docker_val_..._01` | AGENT1_WIN | +2.490 | [+1.804, +3.177] | **8.00s (EMPTY)** | **8.00s (EMPTY)** | **3,728 decisions skipped** |
| `r1_6` (searched) | `docker_val_..._01` | **AGENT2_WIN** | **-0.571** | [-1.138, -0.004] | **8.02s (EMPTY)** | **8.00s (EMPTY)** | **1,488 decisions skipped (LOSS)** |

### Qualification Decision: REJECT CHALLENGER
`RobustPortfolio_v4` failed the mandatory qualification criteria:
1. **Headroom Policy Violation**: Exceeded the $\le 6.0$-second challenger-promotion headroom policy in 100% of measured halves, running the bank completely empty to 8.00s.
2. **Skipped Decisions**: 5,216 total calls were skipped by the judge, forcing check/fold across hundreds of hands.
3. **Outright Match Defeat**: Lost decisively to `r1_6` (-0.571 BB/deal) due to bank exhaustion.

Per the release protocol ("If v4 cannot qualify, retain v3 and finish the release. Do not begin an unlimited optimization cycle"), `RobustPortfolio_v4` is rejected and `Counterplay_v3` is finalized as the tournament release candidate.

---

## 7. Latency, Memory, and Environment Accounting

### Request Latency Distribution (Measured inside Restricted Docker Container)

Benchmarked over 500 actions spanning preflop, flop, turn, and river under container limits:
- **Mean Latency**: 1.06 ms
- **P50 Latency**: 1.00 ms
- **P90 Latency**: 1.37 ms
- **P95 Latency**: 1.51 ms
- **P99 Latency**: 1.84 ms
- **Max Latency**: 2.80 ms (Pass; 357x margin below the 1,000.0 ms hard action timeout limit)
- **Timeouts > 1.0s**: 0 / 500 (0.0%)

Across all 69,802 requests recorded during `Counterplay_v3` container matches:
- **Judge Action Timeouts**: 0
- **Judge Errors**: 0
- **Forfeits**: 0
- **Internal Exceptions**: 0
- **Illegal-Action Fallbacks**: 0

### Image Identity and Network Isolation

- **Docker Image Identity**: `sha256:05ce740f89930fb4ac8800b40f4dc8b065dfb526a349bdd78745d858afd5dcb1` (Local Image ID computed by Docker engine; no remote registry push performed).
- **Network Configuration**:
  - `tools/check_build.sh` smoke test enforces `--network none` (loopback only inside container).
  - Container matches use `-p 5008:5008` bridge port publishing to allow the host referee process to reach the agent HTTP endpoint. The agent initiates zero outbound connections. In tournament Kubernetes pods, both referee and agent share pod loopback without outbound internet access.
- **Memory & Storage**:
  - Resident Memory (RSS): 74.54 MiB / 4,096 MiB (1.82% utilization; >4,020 MiB headroom).
  - Lookup Tables: `data/preflop.npy` (4.52 MB) + `data/pair_triple.npy` (17.99 MB) = 22.51 MB.
  - Image size added on base: 86 MB (< 3,072 MB cap).

---

## 8. Release Artifacts & Handoff

- **Active Selected Release**: `TeamAntigravity / Counterplay_v3`
- **Release Commit SHA**: `5c6adbd96311bae48a7f17fcd2c5f7a92c460282`
- **Review ZIP**: `release/review_bundle_Counterplay_v3.zip` (2.57 MB zip, verified < 20 MB limit).
- **Preserved Rollback**: `DrawAware_v1` (`release/review_bundle_DrawAware_v1.zip`).
