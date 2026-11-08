"""
evaluation/enumerate_max_actions.py - Exact reachable betting tree enumeration for TAMU PLO5.

Enumerates all reachable betting sequences under official rules:
- Starting stacks: 80 chips
- Blinds: 1 (Small Blind) and 2 (Big Blind)
- Raise cap: 4 raises per street
- Pot-limit / half-pot raise mechanics

Determines the exact maximum number of voluntary actions in any legal hand.
"""

from __future__ import annotations

import sys
import os
import hashlib
from typing import List, Tuple, Dict, Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from game import Game, make_deal, Action, Street, BIG_BLIND, STARTING_STACK, RAISE_CAP_PER_STREET


def enumerate_tree():
    deal = make_deal("tree_search", 0)

    # Document engine hash
    engine_path = os.path.join(ROOT_DIR, "game.py")
    with open(engine_path, "rb") as f:
        engine_hash = hashlib.sha256(f.read()).hexdigest()

    print("=" * 80)
    print("BETTING TREE ENUMERATION: TAMU HEADS-UP SHORT DECK PLO5")
    print(f"Engine file: {engine_path}")
    print(f"Engine SHA-256: {engine_hash}")
    print(f"Constants: STARTING_STACK={STARTING_STACK}, BIG_BLIND={BIG_BLIND}, RAISE_CAP={RAISE_CAP_PER_STREET}")
    print("=" * 80)

    # To search efficiently without full exponential blowup of all passive lines:
    # We want to find the maximum possible depth (action count).
    # We can use memoized search or branch-and-bound DFS.
    # Note: Actions that don't reduce stacks (e.g. checks) add 2 actions per street.
    # Raises consume chips. We want to find which combinations of checks, raises, and calls
    # maximize the number of legal actions before players run out of chips or hands terminate.

    max_actions = 0
    longest_history = []
    longest_btn = -1

    # Stack state can be represented by (street, button_seat, to_act, pot, bets[0], bets[1], stacks[0], stacks[1], raises_this_street, acted[0], acted[1])
    visited_depths = {}

    def dfs(actions_played: list[Action], button: int):
        nonlocal max_actions, longest_history, longest_btn

        # Replay to current state
        g = Game(deal, button, hand_index=0)
        for a in actions_played:
            g.apply(a)

        cur_len = len(g.history)
        if cur_len > max_actions:
            max_actions = cur_len
            longest_history = [r.to_dict() for r in g.history]
            longest_btn = button

        if g.is_terminal:
            return

        # Prune if this exact state was reached with >= current depth
        state_key = (
            g.street,
            g.to_act,
            g.pot,
            g.bets[0],
            g.bets[1],
            g.stacks[0],
            g.stacks[1],
            g.raises_this_street,
            g.acted[0],
            g.acted[1],
        )
        if state_key in visited_depths and visited_depths[state_key] >= cur_len:
            return
        visited_depths[state_key] = cur_len

        legal = g.legal_actions()
        # To find longest path faster, explore non-folding actions first
        for act in sorted(legal, key=lambda a: (a == Action.FOLD, a)):
            if act == Action.FOLD:
                continue  # fold immediately terminates, cannot be part of the longest sequence
            actions_played.append(act)
            dfs(actions_played, button)
            actions_played.pop()

    for btn in (0, 1):
        visited_depths.clear()
        dfs([], btn)

    print(f"\n[RESULT] Maximum Reachable Voluntary Actions: {max_actions}")
    print(f"Optimal Button: Seat {longest_btn}")
    print("\nAction-by-Action Trajectory:")
    print(f"{'#':<4} | {'Street':<10} | {'Seat':<6} | {'Action':<12} | {'Amount':<8} | {'Street Total':<12} | {'Pot'}")
    print("-" * 75)

    g_replay = Game(deal, longest_btn, hand_index=0)
    for i, a in enumerate(longest_history):
        act_enum = Action[a["action"]] if isinstance(a["action"], str) else Action(a["action"])
        st_enum = Street[a["street"]] if isinstance(a["street"], str) else Street(a["street"])
        g_replay.apply(act_enum)
        print(f"{i+1:<4} | {st_enum.name:<10} | {a['seat']:<6} | {act_enum.name:<12} | {a['amount']:<8} | {a['street_total']:<12} | {g_replay.pot}")

    return max_actions, longest_history, engine_hash


if __name__ == "__main__":
    enumerate_tree()
