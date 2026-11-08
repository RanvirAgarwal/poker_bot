---
name: export-poker-release
description: Export compatible assets, verify packaging, run smoke tests and check_build.sh, retain rollback candidates.
---

# Export Poker Release Skill

## Purpose
Validates that `agent.py` and its imported dependencies conform to official packaging requirements:
- Validated against official `starter/test_agent.py` test suite
- Validated via `smoke_test.py`
- Pinned dependency constraints checked against `requirements.txt`
- No internet access required at runtime
- All assets bundle within size limits (< 3 GB Docker layer, < 100MB per git file)

## Verification Commands
```powershell
# 1. Run official test suite
.\venv\Scripts\python.exe -m pytest starter\test_agent.py -v

# 2. Run official smoke test
cd starter
..\venv\Scripts\python.exe tools\smoke_test.py
```

## Rollback Protocol
- Always maintain previous best checkpoint in `assets/` and record commit hash in `MEMORY.md`.
