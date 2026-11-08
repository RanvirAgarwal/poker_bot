"""
training/mccfr.py - External-Sampling Monte Carlo Counterfactual Regret Minimization.

Implements ES-MCCFR for heads-up Short Deck PLO5 with discrete abstraction.
"""

from __future__ import annotations

import sys
import os
import random
import pickle
from collections import defaultdict
from typing import Dict, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from game import Game, Deal, Action, Street, make_deal, button_for_deal, default_action
from training.abstraction import get_preflop_bucket, get_postflop_bucket, make_infoset_key
from training.generic_mccfr import GenericMCCFRTrainer, ExtensiveGame

ACTION_TO_CHAR = {
    Action.FOLD: "F",
    Action.CHECK_CALL: "C",
    Action.RAISE_HALF: "H",
    Action.RAISE_POT: "P",
}


def history_str(game: Game) -> str:
    """Compact string encoding of action history."""
    return "".join(ACTION_TO_CHAR[r.action] for r in game.history)


class PLO5ExtensiveGame:
    """Adapter wrapping official Game to implement ExtensiveGame protocol."""

    def __init__(self, game: Game):
        self.game = game

    @property
    def is_terminal(self) -> bool:
        return self.game.is_terminal

    @property
    def to_act(self) -> int:
        return self.game.to_act

    def legal_actions(self) -> Tuple[Action, ...]:
        return self.game.legal_actions()

    def clone(self) -> PLO5ExtensiveGame:
        return PLO5ExtensiveGame(self.game.clone())

    def apply(self, action: Action) -> None:
        self.game.apply(action)

    def payoffs(self, traversing_seat: int) -> float:
        return float(self.game.result().nets[traversing_seat])

    def info_set_key(self, seat: int) -> str:
        hole = self.game.deal.hole_cards[seat]
        if self.game.street == Street.PREFLOP:
            bucket = get_preflop_bucket(hole)
        else:
            visible = [3, 4, 5][self.game.street - 1]
            board = self.game.deal.board[:visible]
            bucket = get_postflop_bucket(hole, board)
        hist = history_str(self.game)
        return make_infoset_key(self.game.street, bucket, hist)


class MCCFRTrainer:
    """External-Sampling MCCFR trainer for Heads-Up Short Deck PLO5.
    
    Directly delegates traversal and regret minimization to GenericMCCFRTrainer,
    ensuring that the update implementation validated against Kuhn analytical ground
    truth is executed identically on PLO5.
    """

    def __init__(self, seed: int = 42):
        self.engine = GenericMCCFRTrainer(seed=seed)

    @property
    def regrets(self):
        return self.engine.regrets

    @property
    def strategy_sum(self):
        return self.engine.strategy_sum

    @property
    def iterations(self) -> int:
        return self.engine.iterations

    @iterations.setter
    def iterations(self, val: int):
        self.engine.iterations = val

    def get_strategy(self, info_set: str, legal_actions: Tuple[Action, ...]) -> Dict[Action, float]:
        """Compute current strategy from positive regrets (Regret Matching)."""
        return self.engine.get_strategy(info_set, legal_actions)

    def get_average_strategy(self, info_set: str, legal_actions: Tuple[Action, ...]) -> Dict[Action, float]:
        """Compute average strategy over all iterations."""
        return self.engine.get_average_strategy(info_set, legal_actions)

    def train_iteration(self, match_seed: str, deal_index: int):
        """Run one iteration of ES-MCCFR: alternately traverse for seat 0 and seat 1."""
        deal = make_deal(match_seed, deal_index)
        button = button_for_deal(deal_index)

        # Traverse for seat 0
        g0 = PLO5ExtensiveGame(Game(deal, button, hand_index=deal_index))
        self.engine.traverse(g0, traversing_seat=0)

        # Traverse for seat 1
        g1 = PLO5ExtensiveGame(Game(deal, button, hand_index=deal_index))
        self.engine.traverse(g1, traversing_seat=1)

        self.engine.iterations += 1

    def save_checkpoint(self, path: str):
        """Serialize average strategy tables to disk."""
        self.engine.save_checkpoint(path)

    def load_checkpoint(self, path: str):
        """Load trained strategy sums from disk."""
        self.engine.load_checkpoint(path)

