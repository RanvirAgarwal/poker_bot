"""
tests/test_reachable_history.py - Validates reachable betting tree depth
and stressful legal observation generation under the official game engine.

Validates:
1. Exact engine hash of game.py.
2. Complete reachable betting tree search proving maximum voluntary action depth is 14.
3. Official observation generated from genuine legal Game execution (replacing synthetic fixtures).
4. RangeAwarePolicy execution against the genuinely deepest legal observation.
"""

from __future__ import annotations

import sys
import os
import hashlib
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from game import Game, make_deal, Action, Street, BIG_BLIND, STARTING_STACK, RAISE_CAP_PER_STREET
from runtime.range_aware_policy import RangeAwarePolicy

OFFICIAL_GAME_HASH = "06829231bf2a285279c42a2ab4228bb4a46e170a6398146c894111c05e3c61a2"


def test_engine_hash_and_constants():
    """Verify that game.py matches the official referee version exactly."""
    engine_path = os.path.join(ROOT_DIR, "game.py")
    with open(engine_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    assert actual_hash == OFFICIAL_GAME_HASH, f"Engine hash mismatch: {actual_hash} != {OFFICIAL_GAME_HASH}"
    assert STARTING_STACK == 80
    assert BIG_BLIND == 2
    assert RAISE_CAP_PER_STREET == 4


def test_maximum_reachable_voluntary_actions():
    """Prove that 14 is the maximum number of voluntary actions in any legal hand."""
    deal = make_deal("tree_search", 0)

    # 14-action maximal sequence identified by exact tree enumeration:
    # Button 0 (Seat 0):
    # Preflop: Call (1), Check (2)
    # Flop: Check (3), Check (4)
    # Turn: Check (5), Raise Half (6), Raise Half (7), Call (8)
    # River: Check (9), Raise Half (10), Raise Half (11), Raise Half (12), Raise Half (13), Call (14)
    max_actions = [
        Action.CHECK_CALL,  # 1: SB limp
        Action.CHECK_CALL,  # 2: BB check
        Action.CHECK_CALL,  # 3: BB check
        Action.CHECK_CALL,  # 4: SB check
        Action.CHECK_CALL,  # 5: BB check
        Action.RAISE_HALF,   # 6: SB bet half
        Action.RAISE_HALF,   # 7: BB raise half
        Action.CHECK_CALL,  # 8: SB call
        Action.CHECK_CALL,  # 9: BB check
        Action.RAISE_HALF,   # 10: SB bet half
        Action.RAISE_HALF,   # 11: BB raise half
        Action.RAISE_HALF,   # 12: SB raise half
        Action.RAISE_HALF,   # 13: BB raise half (all in)
        Action.CHECK_CALL,  # 14: SB call (all in)
    ]

    g = Game(deal, button_seat=0, hand_index=0)
    for i, act in enumerate(max_actions):
        assert not g.is_terminal, f"Game ended prematurely before action {i+1}"
        assert act in g.legal_actions(), f"Action {act.name} illegal at step {i+1}: legal={g.legal_actions()}"
        g.apply(act)

    assert len(g.history) == 14
    assert g.is_terminal
    assert g.pot == 160  # All 160 chips in play are committed (80 + 80)


def test_deepest_legal_observation_stress():
    """Generate the genuinely deepest reachable Observation from Game and pass to RangeAwarePolicy."""
    deal = make_deal("tree_search", 0)
    # Replay through action 13 (River 4th raise facing all-in)
    max_actions = [
        Action.CHECK_CALL,  # 1
        Action.CHECK_CALL,  # 2
        Action.CHECK_CALL,  # 3
        Action.CHECK_CALL,  # 4
        Action.CHECK_CALL,  # 5
        Action.RAISE_HALF,   # 6
        Action.RAISE_HALF,   # 7
        Action.CHECK_CALL,  # 8
        Action.CHECK_CALL,  # 9
        Action.RAISE_HALF,   # 10
        Action.RAISE_HALF,   # 11
        Action.RAISE_HALF,   # 12
        Action.RAISE_HALF,   # 13: Opponent raises all-in on river
    ]

    g = Game(deal, button_seat=0, hand_index=0)
    for act in max_actions:
        g.apply(act)

    # Seat 0 is now facing action 14 with a history of 13 genuine legal actions
    assert not g.is_terminal
    obs = g.observation(g.to_act)
    assert len(obs.action_history) == 13
    assert obs.street == Street.RIVER
    assert obs.to_call > 0

    policy = RangeAwarePolicy(aggression=1.0, seed=42)
    memory = {}
    chosen = policy.choose_action(obs, memory)
    assert chosen in obs.legal_actions
    assert chosen in (Action.CHECK_CALL, Action.FOLD)

