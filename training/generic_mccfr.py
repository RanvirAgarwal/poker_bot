"""
training/generic_mccfr.py - Reusable, game-agnostic External-Sampling MCCFR engine.

Shared core algorithm used for both toy games (Kuhn, Leduc) and heads-up Short Deck PLO5.
Ensures algorithm correctness verified on small games applies directly to full game.

Changelog:
- F5 fix: strategy_sum accumulation now weights by own reach probability at the traversing
  player's node, as required by external-sampling MCCFR (Lanctot et al. 2009, Algorithm 2).
  Previously accumulated raw strat[a] without reach weighting, producing incorrect average strategy.
- F6 fix: save_checkpoint now includes regrets and RNG state; load_checkpoint restores both,
  enabling exact deterministic resume from any checkpoint.
- Added train_iteration() convenience method for external callers.
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
    """Game-agnostic External-Sampling Monte Carlo Counterfactual Regret Minimization.

    Algorithm reference: Lanctot et al. 2009, "Monte Carlo Sampling for Regret Minimization
    in Extensive Games", Algorithm 2 (External Sampling).

    Key invariant (F5 fix): For the traversing player's nodes, strategy_sum[a] is accumulated
    weighted by the traversing player's own reach probability (pi_i in Zinkevich notation).
    This is required for the average strategy to converge to a Nash equilibrium strategy.

    Without reach weighting, all traversals contribute equally regardless of how often that
    node is actually reached, biasing the average strategy toward uniform.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        # Regret tables: info_set -> {action: cumulative_regret}
        self.regrets: Dict[str, Dict[Any, float]] = defaultdict(lambda: defaultdict(float))
        # Strategy sum tables: info_set -> {action: cumulative_strategy (reach-weighted)}
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

    def traverse(self, game: ExtensiveGame, traversing_seat: int,
                 reach_prob: float = 1.0) -> float:
        """Recursive external-sampling MCCFR traversal.

        Args:
            game: Current game state.
            traversing_seat: The player whose regrets we are updating this iteration.
            reach_prob: The traversing player's own reach probability to this node
                        (product of their own strategy choices along the path).
                        Used to weight strategy_sum accumulation (F5 fix).

        Returns:
            Counterfactual value of this node for the traversing player.
        """
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
                # Traversing player explores ALL actions; reach probability multiplied by strat[a]
                action_values[a] = self.traverse(next_game, traversing_seat,
                                                  reach_prob * strat[a])

            node_value = sum(strat[a] * action_values[a] for a in legal_actions)

            # Accumulate regrets and strategy
            for a in legal_actions:
                regret = action_values[a] - node_value
                self.regrets[info_set][a] += regret
                # F5 fix: weight by own reach probability (pi_i in Zinkevich notation)
                # This ensures the average strategy converges correctly.
                # reach_prob here is the probability of reaching THIS node under the traversing
                # player's OWN strategy (before the action choice at this node).
                self.strategy_sum[info_set][a] += reach_prob * strat[a]

            return node_value
        else:
            probs = [strat[a] for a in legal_actions]
            sampled_action = self.rng.choices(legal_actions, weights=probs, k=1)[0]
            next_game = game.clone()
            next_game.apply(sampled_action)
            # Opponent actions do not change traversing player's reach prob
            return self.traverse(next_game, traversing_seat, reach_prob)

    def train_iteration(self, game_root: ExtensiveGame) -> None:
        """Run one full MCCFR iteration (traverse for each player seat in turn).

        Convenience method: creates a fresh game clone per traversing seat.
        """
        # Determine number of seats from the game (assume 2-player: seats 0 and 1)
        for seat in range(2):
            g = game_root.clone()
            self.traverse(g, seat)
        self.iterations += 1

    def save_checkpoint(self, path: str):
        """Save complete trainer state for exact deterministic resume.

        F6 fix: includes regrets and RNG state in addition to strategy_sum.
        """
        with open(path, "wb") as f:
            pickle.dump({
                "iterations": self.iterations,
                "strategy_sum": {k: dict(v) for k, v in self.strategy_sum.items()},
                "node_visits": dict(self.node_visits),
                # F6 fix: save regrets and RNG state
                "regrets": {k: dict(v) for k, v in self.regrets.items()},
                "rng_state": self.rng.getstate(),
            }, f, protocol=pickle.HIGHEST_PROTOCOL)

    def load_checkpoint(self, path: str):
        """Load complete trainer state.

        F6 fix: restores regrets and RNG state for deterministic resume.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.iterations = data["iterations"]
        self.strategy_sum.clear()
        for k, v in data["strategy_sum"].items():
            self.strategy_sum[k].update(v)
        self.node_visits = defaultdict(int, data.get("node_visits", {}))
        # F6 fix: restore regrets
        self.regrets.clear()
        for k, v in data.get("regrets", {}).items():
            self.regrets[k].update(v)
        # F6 fix: restore RNG state
        rng_state = data.get("rng_state")
        if rng_state is not None:
            self.rng.setstate(rng_state)
