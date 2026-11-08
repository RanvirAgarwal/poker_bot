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

ACTION_TO_CHAR = {
    Action.FOLD: "F",
    Action.CHECK_CALL: "C",
    Action.RAISE_HALF: "H",
    Action.RAISE_POT: "P",
}


def history_str(game: Game) -> str:
    """Compact string encoding of action history."""
    return "".join(ACTION_TO_CHAR[r.action] for r in game.history)


class MCCFRTrainer:
    """External-Sampling MCCFR trainer for Heads-Up Short Deck PLO5."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        # Regret tables: info_set -> {Action: cumulative_regret}
        self.regrets: Dict[str, Dict[Action, float]] = defaultdict(lambda: defaultdict(float))
        # Strategy sum tables for average policy: info_set -> {Action: cumulative_strategy}
        self.strategy_sum: Dict[str, Dict[Action, float]] = defaultdict(lambda: defaultdict(float))
        self.iterations = 0

    def get_strategy(self, info_set: str, legal_actions: Tuple[Action, ...]) -> Dict[Action, float]:
        """Compute current strategy from positive regrets (Regret Matching)."""
        regrets = self.regrets[info_set]
        pos_regrets = {a: max(0.0, regrets[a]) for a in legal_actions}
        total = sum(pos_regrets.values())

        if total > 0:
            return {a: pos_regrets[a] / total for a in legal_actions}
        else:
            # Default to uniform over legal actions
            n = len(legal_actions)
            return {a: 1.0 / n for a in legal_actions}

    def get_average_strategy(self, info_set: str, legal_actions: Tuple[Action, ...]) -> Dict[Action, float]:
        """Compute average strategy over all iterations."""
        sums = self.strategy_sum[info_set]
        total = sum(sums[a] for a in legal_actions)
        if total > 0:
            return {a: sums[a] / total for a in legal_actions}
        return {a: 1.0 / len(legal_actions) for a in legal_actions}

    def _get_bucket(self, game: Game, seat: int) -> int:
        hole = game.deal.hole_cards[seat]
        if game.street == Street.PREFLOP:
            return get_preflop_bucket(hole)
        else:
            visible = [3, 4, 5][game.street - 1]
            board = game.deal.board[:visible]
            return get_postflop_bucket(hole, board)

    def _traverse(self, game: Game, traversing_seat: int) -> float:
        """Recursive ES-MCCFR traversal."""
        if game.is_terminal:
            # Payoff to traversing player in chips
            return float(game.result().nets[traversing_seat])

        current_seat = game.to_act
        legal_actions = game.legal_actions()
        if not legal_actions:
            return 0.0

        bucket = self._get_bucket(game, current_seat)
        hist = history_str(game)
        info_set = make_infoset_key(game.street, bucket, hist)
        strategy = self.get_strategy(info_set, legal_actions)

        if current_seat == traversing_seat:
            # Traversing player: explore ALL actions
            action_values = {}
            for a in legal_actions:
                next_game = game.clone()
                next_game.apply(a)
                action_values[a] = self._traverse(next_game, traversing_seat)

            # Node value
            node_value = sum(strategy[a] * action_values[a] for a in legal_actions)

            # Accumulate counterfactual regrets and average strategy
            for a in legal_actions:
                regret = action_values[a] - node_value
                self.regrets[info_set][a] += regret
                self.strategy_sum[info_set][a] += strategy[a]

            return node_value
        else:
            # Opponent node: sample single action according to strategy
            probs = [strategy[a] for a in legal_actions]
            sampled_action = self.rng.choices(legal_actions, weights=probs, k=1)[0]

            next_game = game.clone()
            next_game.apply(sampled_action)
            return self._traverse(next_game, traversing_seat)

    def train_iteration(self, match_seed: str, deal_index: int):
        """Run one iteration of ES-MCCFR: alternately traverse for seat 0 and seat 1."""
        deal = make_deal(match_seed, deal_index)
        button = button_for_deal(deal_index)

        # Traverse for seat 0
        g0 = Game(deal, button, hand_index=deal_index)
        self._traverse(g0, traversing_seat=0)

        # Traverse for seat 1
        g1 = Game(deal, button, hand_index=deal_index)
        self._traverse(g1, traversing_seat=1)

        self.iterations += 1

    def save_checkpoint(self, path: str):
        """Serialize average strategy tables to disk."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # Convert defaultdicts to regular dicts for clean pickling
        model = {
            "iterations": self.iterations,
            "strategy_sum": {k: dict(v) for k, v in self.strategy_sum.items()},
        }
        with open(path, "wb") as f:
            pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load_checkpoint(self, path: str):
        """Load trained strategy sums from disk."""
        with open(path, "rb") as f:
            model = pickle.load(f)
        self.iterations = model["iterations"]
        self.strategy_sum.clear()
        for k, v in model["strategy_sum"].items():
            self.strategy_sum[k].update(v)

