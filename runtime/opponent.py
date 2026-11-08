"""
runtime/opponent.py - Opponent modeling from observed hand results.

Tracks opponent behavior patterns within a single half (memory resets
between halves per tournament rules).
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "starter"))

from game import Action, HandResult


class OpponentModel:
    """Tracks opponent tendencies from observed actions and showdowns.

    Stored entirely in the memory dict, so state resets each half.
    """

    @staticmethod
    def init_memory(memory: dict) -> None:
        """Initialize opponent tracking fields in memory."""
        memory["opp"] = {
            "hands_seen": 0,
            "showdowns": 0,
            "folds_observed": 0,  # we can't directly see their folds as actions
            "wins": 0,
            "losses": 0,
            "splits": 0,
            "total_net": 0,
            "showdown_wins": 0,
            "vol_put_in": 0,  # voluntary chips put in (proxy for aggression)
            "big_pots_won": 0,
            "big_pots_lost": 0,
        }

    @staticmethod
    def update(result: HandResult, memory: dict) -> None:
        """Update opponent model from a hand result."""
        opp = memory.get("opp")
        if opp is None:
            OpponentModel.init_memory(memory)
            opp = memory["opp"]

        opp["hands_seen"] += 1
        opp["total_net"] -= result.my_net  # opp's net is inverse of ours

        if result.winner == "opp":
            opp["wins"] += 1
        elif result.winner == "me":
            opp["losses"] += 1
        else:
            opp["splits"] += 1

        if result.went_to_showdown:
            opp["showdowns"] += 1
            if result.winner == "opp":
                opp["showdown_wins"] += 1

        # Track big pots (>= 20 chips)
        if result.pot >= 20:
            if result.winner == "opp":
                opp["big_pots_won"] += 1
            elif result.winner == "me":
                opp["big_pots_lost"] += 1

    @staticmethod
    def get_stats(memory: dict) -> dict:
        """Get computed opponent statistics."""
        opp = memory.get("opp", {})
        hands = max(1, opp.get("hands_seen", 0))
        showdowns = max(1, opp.get("showdowns", 0))

        return {
            "aggression": opp.get("wins", 0) / hands,  # crude proxy
            "showdown_rate": opp.get("showdowns", 0) / hands,
            "showdown_win_rate": opp.get("showdown_wins", 0) / showdowns,
            "avg_net_per_hand": opp.get("total_net", 0) / hands,
            "hands_seen": opp.get("hands_seen", 0),
        }

