# Project Instructions

**Before any substantial work, read `MEMORY.md` in this directory.**

Then read the relevant references for your current task:
- Architecture: `docs/ARCHITECTURE.md`
- Decisions: `docs/DECISIONS.md`
- Skills: `.agents/skills/*/SKILL.md`
- Experiment reports: `reports/`

This is a TAMU Datathon heads-up Short Deck PLO5 poker bot project.
The official starter is in `starter/` (read-only reference).
Our implementation lives in `runtime/`, `training/`, `opponents/`, `evaluation/`.
The tournament entry point is `agent.py` at the project root.

Key constraints:
- 1 CPU, 4 GB RAM, no internet at runtime
- 8-second charged time bank per half, 1-second request limit
- 15-second startup, 5 errors forfeit
- Memory dict resets each half (fresh server process per half)
- 36-card Short Deck, 5 hole cards, 5 board cards, exactly 2+3 Omaha selection
- Flush > Full House, Trips > Straight in Short Deck rankings
- 4 discrete actions: FOLD, CHECK_CALL, RAISE_HALF, RAISE_POT
- 80-chip starting stacks, 1/2 blinds, 4 raises per street cap

