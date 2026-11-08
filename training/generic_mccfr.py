"""
training/generic_mccfr.py - Reusable, game-agnostic External-Sampling MCCFR engine.

Shared core algorithm used for both toy games (Kuhn, Leduc) and heads-up Short Deck PLO5.
Ensures algorithm correctness verified on small games applies directly to full game.
"""

from __future__ import annotations

import random
import pickle
from collections import defaultdict
from typing import Dict, Any, Sequence, Protocol, List


class ExtensiveGame(Protocol):
    """Abstract interface required by the generic ES-MCCFR engine."""
    @property
    def is_terminal(self) -> bool: ...
    @property
    def to_act(self) -> int: ...
    def legal_actions(self) -> Sequence[Any]: ...
    def clone(self) -> ExtensiveGame: ...
    def apply(self, action: Any) -> None: ...
    def payoffs(self, traversing_seat: int) -> float: ...
    def info_set_key(self, seat: int) -> str: ...


class GenericMCCFRTrainer:
    """Game-agnostic External-Sampling Monte Carlo Counterfactual Regret Minimization."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        # Regret tables: info_set -> {action: cumulative_regret}
        self.regrets: Dict[str, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))
        # Strategy sum tables: info_set -> {action: cumulative_strategy}
        self.strategy_sum: Dict[str, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))
        # Information set visit counter
        self.node_visits: Dict[str, int] = defaultdict(int)
        self.iterations = 0

    def get_strategy(self, info_set: str, legal_actions: Sequence[Any]) -> Dict[Any, float]:
        """Compute current policy from positive regrets via Regret Matching."""
        regrets = self.regrets[info_set]
        pos_regrets = {a: max(0.0, regrets[a]) for a in legal_actions}
        total = sum(pos_regrets.values())
        if total > 0:
            return {a: pos_regrets[a] / total for a in legal_actions}
        n = len(legal_actions)
        return {a: 1.0 / n for a in legal_actions}

    def get_average_strategy(self, info_set: str, legal_actions: Sequence[Any]) -> Dict[Any, float]:
        """Compute normalized average strategy accumulated over all training iterations."""
        sums = self.strategy_sum[info_set]
        total = sum(sums.get(a, 0.0) for a in legal_actions)
        if total > 0:
            return {a: sums.get(a, 0.0) / total for a in legal_actions}
        return {a: 1.0 / len(legal_actions) for a in legal_actions}

    def traverse(self, game: ExtensiveGame, traversing_seat: int) -> float:
        """Recursive external-sampling MCCFR traversal."""
        if game.is_terminal:
            return game.payoffs(traversing_seat)

        current_seat = game.to_act
        legal_actions = list(game.legal_actions())
        if not legal_actions:
            return 0.0

        info_set = game.info_set_key(current_seat)
        strat = self.get_strategy(info_set, legal_actions)
        self.node_visits[info_set] += 1

        if current_seat == traversing_seat:
            action_values = {}
            for a in legal_actions:
                next_game = game.clone()
                next_game.apply(a)
                action_values[a] = self.traverse(next_game, traversing_seat)

            node_value = sum(strat[a] * action_values[a] for a in legal_actions)

            # Accumulate regrets and strategy
            for a in legal_actions:
                regret = action_values[a] - node_value
                self.regrets[info_set][a] += regret
                self.strategy_sum[info_set][a] += strat[a]

            return node_value
        else:
            probs = [strat[a] for a in legal_actions]
            sampled_action = self.rng.choices(legal_actions, weights=probs, k=1)[0]
            next_game = game.clone()
            next_game.apply(sampled_action)
            return self.traverse(next_game, traversing_seat)

    def save_checkpoint(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({
                "iterations": self.iterations,
                "strategy_sum": {k: dict(v) for k, v in self.strategy_sum.items()},
                "node_visits": dict(self.node_visits),
            }, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load_checkpoint(self, path: str):
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.iterations = data["iterations"]
        self.strategy_sum.clear()
        for k, v in data["strategy_sum"].items():
            self.strategy_sum[k].update(v)
        self.node_visits = defaultdict(int, data.get("node_visits", {}))

