"""
opponents/draw_aware_opponent.py - Independent draw-aware benchmark opponent.

Implemented separately from runtime/draw_aware_policy.py to provide an independent
adversarial test opponent for draw-awareness comparisons.
"""

from __future__ import annotations

import sys
import os
import random
from typing import Sequence, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import NUM_CARDS, get_table
from game import Action, Observation, Street
from runtime.features import omaha_score_fast, precompute_board_masks, preflop_hand_quality


class DrawAwareOpponent:
    """Independent draw-aware opponent using Monte Carlo complete runout rollouts."""

    def __init__(self, seed: int = 505, num_samples: int = 25):
        self.rng = random.Random(seed)
        self.num_samples = num_samples

    def _estimate_showdown_equity(self, hole: Sequence[int], board: Sequence[int]) -> float:
        """Estimate showdown equity by rolling out random opponent hands and future board cards."""
        if len(board) == 0:
            return preflop_hand_quality(hole)

        used = set(hole) | set(board)
        remaining = [c for c in range(NUM_CARDS) if c not in used]
        needed_cards = 5 - len(board)
        table = get_table()

        wins = 0.0
        ties = 0.0
        n_samples = self.num_samples

        for _ in range(n_samples):
            opp_hole = self.rng.sample(remaining, 5)
            if needed_cards > 0:
                rem_board = [c for c in remaining if c not in opp_hole]
                runout = self.rng.sample(rem_board, needed_cards)
                full_board = list(board) + runout
                bm = precompute_board_masks(full_board)
            else:
                bm = precompute_board_masks(board)

            my_sc = omaha_score_fast(hole, bm, table)
            opp_sc = omaha_score_fast(opp_hole, bm, table)
            if my_sc > opp_sc:
                wins += 1.0
            elif my_sc == opp_sc:
                ties += 1.0

        return (wins + 0.5 * ties) / n_samples

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        equity = self._estimate_showdown_equity(obs.hole_cards, obs.board)

        # Preflop logic
        if obs.street == Street.PREFLOP:
            if obs.to_call > 0:
                if equity > 0.65:
                    if Action.RAISE_POT in obs.legal_actions:
                        return Action.RAISE_POT
                    return Action.CHECK_CALL
                if equity > 0.40 and pot_odds < equity * 0.9:
                    return Action.CHECK_CALL
                return Action.FOLD
            else:
                if equity > 0.55 and Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                return Action.CHECK_CALL

        # Postflop logic based on true draw-aware showdown equity
        if obs.to_call > 0:
            if equity > 0.75:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                return Action.CHECK_CALL
            if equity > 0.55:
                if Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.4:
                    return Action.RAISE_HALF
                return Action.CHECK_CALL
            if equity > pot_odds + 0.05:
                return Action.CHECK_CALL
            return Action.FOLD

        # Unopened postflop
        if equity > 0.65:
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
        elif equity > 0.45:
            if Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.5:
                return Action.RAISE_HALF

        return Action.CHECK_CALL
