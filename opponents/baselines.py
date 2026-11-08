"""
opponents/baselines.py - Baseline opponent implementations for evaluation.

These are independent implementations (not wrappers around the starter bots)
for use in our local evaluation framework.
"""

from __future__ import annotations

import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "starter"))

from game import Action, Observation, HandResult, Street


class CheckFoldBot:
    """The default starter bot: checks when free, folds to any bet."""
    name = "CheckFold"

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.to_call == 0:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class CallingStationBot:
    """Always calls. Never folds, never raises."""
    name = "CallingStation"

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        return Action.CHECK_CALL

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class RandomBot:
    """Uniformly random legal action."""
    name = "Random"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        return self.rng.choice(obs.legal_actions)

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class AlwaysRaiseBot:
    """Raises pot when possible, otherwise calls."""
    name = "AlwaysRaise"

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if Action.RAISE_POT in obs.legal_actions:
            return Action.RAISE_POT
        if Action.RAISE_HALF in obs.legal_actions:
            return Action.RAISE_HALF
        return Action.CHECK_CALL

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class EquityCallBot:
    """Calls when estimated equity exceeds pot odds, folds otherwise.

    A simple but non-trivial opponent that makes mathematical decisions.
    Uses the starter evaluator for postflop equity.
    """
    name = "EquityCall"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        from runtime.features import hand_strength_sampled, preflop_hand_quality

        # Get equity estimate
        if obs.street == Street.PREFLOP:
            equity = preflop_hand_quality(obs.hole_cards)
        else:
            equity = hand_strength_sampled(
                obs.hole_cards, obs.board,
                num_samples=50, rng=self.rng
            )

        if obs.to_call == 0:
            # Bet with strong hands
            if equity > 0.6 and Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        if equity > pot_odds:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


# Registry of all baseline bots
BASELINE_REGISTRY = {
    "check_fold": CheckFoldBot,
    "calling_station": CallingStationBot,
    "random": RandomBot,
    "always_raise": AlwaysRaiseBot,
    "equity_call": EquityCallBot,
}

