"""
runtime/policy.py - Heuristic poker policy based on hand strength and game state.

This is the initial "Milestone A" policy: a hand-strength-driven heuristic
that makes reasonable decisions using equity estimation, position, and pot odds.

This will be replaced/augmented by CFR-trained strategies in later milestones.
"""

from __future__ import annotations

import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "starter"))

from game import Action, Observation, Street
from runtime.features import extract_features, hand_strength_sampled, preflop_hand_quality


class HeuristicPolicy:
    """A hand-strength-based heuristic policy.

    Strategy overview:
    - Preflop: play based on hand quality (pair presence, high cards, suitedness)
    - Postflop: play based on estimated equity vs random opponent range
    - Use pot odds to decide calls
    - Raise strong hands, call medium hands, fold weak hands
    - Position-aware: more aggressive on button
    """

    def __init__(self, aggression: float = 1.0, seed: int | None = None):
        """
        Args:
            aggression: multiplier for raise thresholds (>1 = tighter, <1 = looser)
            seed: RNG seed for mixed strategies
        """
        self.aggression = aggression
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        """Select action based on hand strength and game context."""
        # Always check when free
        if obs.to_call == 0 and Action.RAISE_HALF not in obs.legal_actions:
            return Action.CHECK_CALL

        features = self._fast_features(obs, memory)
        strength = features["hand_strength"]
        is_btn = obs.is_button
        street = obs.street

        # Pot odds calculation
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)

        if street == Street.PREFLOP:
            return self._preflop_action(obs, strength, is_btn, pot_odds)
        else:
            return self._postflop_action(obs, strength, is_btn, pot_odds, features)

    def _fast_features(self, obs: Observation, memory: dict) -> dict:
        """Extract features with caching for speed."""
        if obs.street == Street.PREFLOP:
            strength = preflop_hand_quality(obs.hole_cards)
        else:
            # Use fewer samples for speed in early streets
            n_samples = 100 if obs.street == Street.FLOP else 80
            strength = hand_strength_sampled(
                obs.hole_cards, obs.board,
                num_samples=n_samples, rng=self.rng
            )
        return {"hand_strength": strength, "street": obs.street}

    def _preflop_action(self, obs: Observation, strength: float,
                        is_btn: bool, pot_odds: float) -> Action:
        """Preflop strategy based on hand quality."""
        # Position adjustment
        pos_boost = 0.05 if is_btn else 0.0

        # Facing a raise
        if obs.to_call > 0:
            adj_strength = strength + pos_boost

            # Strong hands: re-raise
            if adj_strength > 0.65 * self.aggression:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
                return Action.CHECK_CALL

            # Medium hands: call if pot odds are good
            if adj_strength > 0.35 * self.aggression:
                if pot_odds < adj_strength * 0.8:
                    return Action.CHECK_CALL
                # Mix in some calls with marginal hands
                if self.rng.random() < 0.3:
                    return Action.CHECK_CALL
                return Action.FOLD

            # Weak hands: mostly fold, occasional bluff
            if self.rng.random() < 0.08:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                return Action.CHECK_CALL
            return Action.FOLD

        # Opening/limping (to_call == 0)
        adj_strength = strength + pos_boost

        # Strong hands: raise
        if adj_strength > 0.50 * self.aggression:
            if Action.RAISE_POT in obs.legal_actions:
                if adj_strength > 0.65:
                    return Action.RAISE_POT
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Medium hands: raise or check depending on position
        if adj_strength > 0.30:
            if is_btn and Action.RAISE_HALF in obs.legal_actions:
                if self.rng.random() < 0.5:
                    return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Weak hands: check
        return Action.CHECK_CALL

    def _postflop_action(self, obs: Observation, strength: float,
                         is_btn: bool, pot_odds: float,
                         features: dict) -> Action:
        """Postflop strategy based on equity estimation."""
        pos_boost = 0.03 if is_btn else 0.0
        adj_strength = strength + pos_boost

        # SPR (stack-to-pot ratio) affects willingness to commit
        spr = obs.my_stack / max(1, obs.pot)

        if obs.to_call > 0:
            # Facing a bet
            # Very strong: raise
            if adj_strength > 0.75:
                if Action.RAISE_POT in obs.legal_actions:
                    if adj_strength > 0.85 or spr < 2:
                        return Action.RAISE_POT
                    return Action.RAISE_HALF
                return Action.CHECK_CALL

            # Strong: call or raise
            if adj_strength > 0.55:
                if adj_strength > 0.65 and Action.RAISE_HALF in obs.legal_actions:
                    if self.rng.random() < 0.3:
                        return Action.RAISE_HALF
                return Action.CHECK_CALL

            # Medium: call if pot odds are favorable
            if adj_strength > pot_odds + 0.05:
                return Action.CHECK_CALL

            # Marginal: occasional call (implied odds approximation)
            if adj_strength > 0.30 and pot_odds < 0.25:
                if self.rng.random() < 0.25:
                    return Action.CHECK_CALL

            # Bluff occasionally on river when it's cheap
            if obs.street == Street.RIVER and obs.to_call <= 4:
                if self.rng.random() < 0.1:
                    return Action.CHECK_CALL

            return Action.FOLD

        # Checking (no bet to call)
        # Strong: bet/raise
        if adj_strength > 0.65:
            if Action.RAISE_POT in obs.legal_actions:
                if adj_strength > 0.80:
                    return Action.RAISE_POT
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Medium-strong: bet sometimes (value + protection)
        if adj_strength > 0.50:
            if Action.RAISE_HALF in obs.legal_actions:
                if self.rng.random() < 0.5:
                    return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Medium: mostly check, occasional small bet
        if adj_strength > 0.35:
            if Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.15:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Weak: check, occasional bluff
        if adj_strength < 0.20 and Action.RAISE_POT in obs.legal_actions:
            if self.rng.random() < 0.07:
                return Action.RAISE_POT
        return Action.CHECK_CALL

