---
name: verify-poker-rules
description: Validate poker ranking, Omaha 2+3 selection, raises, all-ins, observations, and simulator agreement with official source.
---

# Verify Poker Rules Skill

## Purpose
Validates all game mechanics, Short Deck ranking anomalies (Flush > Full House, Trips > Straight, A-6-7-8-9 wheel), exact 2-hole + 3-board Omaha selection, raise sizing, and deterministic dealing.

## Triggers
- When rules, hand scoring, or state transitions are updated
- Before training runs to ensure simulation correctness
- Before any candidate promotion or release

## Verification Commands
```powershell
# Run the complete rule correctness test suite
cd c:\Users\ranvi\poker_bot
.\venv\Scripts\python.exe -m pytest tests\test_rules.py -v
```

## Expected Outputs & Success Conditions
- All test items pass with 0 failures:
  - `test_flush_beats_full_house` -> PASSED
  - `test_trips_beats_straight` -> PASSED
  - `test_wheel_straight` -> PASSED
  - `test_straight_flush_beats_four_of_a_kind` -> PASSED
  - `test_must_use_exactly_two_hole_cards` -> PASSED
  - `test_raise_cap` (max 4 per street) -> PASSED
  - `test_deal_has_no_duplicate_cards` -> PASSED
  - Zero exceptions, zero warnings
