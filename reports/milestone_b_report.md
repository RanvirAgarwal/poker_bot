# Milestone B Experiment & Audit Report: Full-Length Tournament Verification, CFR Audit, and Opponent Population

## Executive Summary
This report documents the rigorous verification, mathematical audit, empirical learning curve, and full-length duplicate tournament matches conducted for our heads-up Short Deck PLO5 bot.

1. **Loader Audit**: Established that the starter's `starter/test_agent.py` previously exercised `starter/agent.py`. Staged official referee files at project root and verified that `tests/test_agent_official.py` exercises our actual candidate `C:\Users\ranvi\poker_bot\agent.py` (`TeamAntigravity / EquityBot_v1`), achieving **12/12 PASSED**.
2. **Container & Build Status**: Docker CLI 29.2.1 is present on the host, but the Docker Desktop daemon is not currently active (`pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`). Containerized build verification via `tools/check_build.sh` is explicitly marked **outstanding**.
3. **Full-Length Tournament Duplicate Matches**: Ran official 1,000-deal duplicate matches (2,000 hands total) with fresh Python server processes spawned separately for Half 1 and Half 2:
   - Vs `CallingStation`: **+12.018 BB/deal**, 95% CI **[+11.033, +13.004] BB/deal** $\rightarrow$ **`AGENT1_WIN`** (1.0 pt).
   - Thinking time: Half 1 = 3.43s / 8.00s; Half 2 = 1.31s / 8.00s. **0 operational errors across 8,001 HTTP requests**.
4. **Mathematical CFR Audit**: Validated our ES-MCCFR engine on Kuhn Poker, proving convergence to analytical Nash equilibrium (game value $\to -1/18 \approx -0.0556$, Queen checks, Jack folds, King calls).
5. **Coverage Audit**: Tested 2k vs 10k CFR checkpoints on held-out deals:
   - 2k checkpoint: 48,421 InfoSets, 97.1% coverage (81.1% on River, 18.9% fallback).
   - 10k checkpoint: 84,492 InfoSets, **99.5% coverage (96.2% on River, 0.5% overall fallback)**.
6. **Expanded 12-Opponent Benchmark**: Evaluated `EquityBot_v1`, `CFRBot_10k`, and `HybridPolicy` across 12 diverse opponents and attackers. `EquityBot_v1` scored **9.0 / 12 points (75.0%)**, outperforming `HybridPolicy` (7.5 pts) and `CFRBot_10k` (6.5 pts). `EquityBot_v1` is strictly preserved as the active tournament candidate.
