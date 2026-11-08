"""
opponents/baselines.py - Baseline and advanced opponent implementations for evaluation.

Includes:
- Official reference baselines (CheckFold, CallingStation, Random, AlwaysRaise)
- Guide's cheap-call baseline fixture
- Size-aware equity bots
- Action-conditioned range bots
- Adaptive exploiter opponents
"""

from __future__ import annotations

import random
import sys
import os
from typing import Sequence

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import NUM_CARDS, get_table, omaha_score, category_of
from game import Action, Observation, HandResult, Street
from runtime.features import omaha_best_score, hand_strength_sampled, preflop_hand_quality


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


class GuideCheapCallBot:
    """Participant Guide baseline fixture:
    Checks when free, calls if the bet to call is small (<= 4 chips), folds when expensive."""
    name = "GuideCheapCall"

    def __init__(self, cheap_threshold: int = 4):
        self.cheap_threshold = cheap_threshold

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.to_call == 0:
            return Action.CHECK_CALL
        if obs.to_call <= self.cheap_threshold:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class EquityCallBot:
    """Calls when estimated equity exceeds pot odds, folds otherwise."""
    name = "EquityCall"

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.street == Street.PREFLOP:
            equity = preflop_hand_quality(obs.hole_cards)
        else:
            equity = hand_strength_sampled(
                obs.hole_cards, obs.board,
                num_samples=50, rng=self.rng
            )

        if obs.to_call == 0:
            if equity > 0.65 and Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        if equity > pot_odds:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class SizeAwareEquityBot:
    """Size-aware equity bot:
    Differentiates between RAISE_HALF (value/protection) and RAISE_POT (nuts/monsters).
    Folds when equity is significantly lower than pot odds."""
    name = "SizeAwareEquity"

    def __init__(self, seed: int = 123):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.street == Street.PREFLOP:
            equity = preflop_hand_quality(obs.hole_cards)
        else:
            equity = hand_strength_sampled(
                obs.hole_cards, obs.board,
                num_samples=75, rng=self.rng
            )

        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)

        if obs.to_call == 0:
            if equity >= 0.80 and Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if equity >= 0.60 and Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Facing a bet
        if equity >= 0.85 and Action.RAISE_POT in obs.legal_actions:
            return Action.RAISE_POT
        if equity >= 0.70 and Action.RAISE_HALF in obs.legal_actions:
            return Action.RAISE_HALF
        if equity >= pot_odds:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class ActionConditionedRangeBot:
    """Conditions opponent range on observed betting actions:
    If opponent raised, assumes opponent holds higher quality preflop hand.
    Estimates equity against conditioned opponent range."""
    name = "ActionConditionedRange"

    def __init__(self, seed: int = 777):
        self.rng = random.Random(seed)

    def _estimate_conditioned_equity(self, obs: Observation, num_samples: int = 60) -> float:
        if obs.street == Street.PREFLOP:
            return preflop_hand_quality(obs.hole_cards)

        # Count opponent raises in history
        opp_raises = sum(1 for a in obs.action_history if not a.is_me and a.action in (Action.RAISE_HALF, Action.RAISE_POT))

        # Sample opponent hands conditioned on raise count
        my_score = omaha_best_score(obs.hole_cards, obs.board)
        used = set(obs.hole_cards) | set(obs.board)
        remaining = [c for c in range(NUM_CARDS) if c not in used]

        # If opponent raised, filter candidate hands to those with above-average quality
        candidate_pool = []
        for _ in range(num_samples * 3):
            cand = self.rng.sample(remaining, 5)
            q = preflop_hand_quality(cand)
            if opp_raises == 0 or (opp_raises == 1 and q >= 0.35) or (opp_raises >= 2 and q >= 0.50):
                candidate_pool.append(cand)
                if len(candidate_pool) >= num_samples:
                    break

        if not candidate_pool:
            candidate_pool = [self.rng.sample(remaining, 5) for _ in range(num_samples)]

        wins = 0
        ties = 0
        for opp_hole in candidate_pool:
            opp_score = omaha_best_score(opp_hole, obs.board)
            if my_score > opp_score:
                wins += 1
            elif my_score == opp_score:
                ties += 1

        return (wins + 0.5 * ties) / len(candidate_pool)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        equity = self._estimate_conditioned_equity(obs)
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)

        if obs.to_call == 0:
            if equity > 0.70 and Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        if equity > 0.85 and Action.RAISE_POT in obs.legal_actions:
            return Action.RAISE_POT
        if equity > pot_odds + 0.05:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class AdaptiveExploiterBot:
    """Tracks opponent fold and aggression tendencies in memory:
    - If opponent folds frequently (> 50% of finished hands), bluffs with raises.
    - If opponent calls everything, stops bluffing and only value-bets nuts.
    - If opponent is hyper-aggressive, traps with checks and calls down with strong holdings."""
    name = "AdaptiveExploiter"

    def __init__(self, seed: int = 999):
        self.rng = random.Random(seed)

    def new_half(self, config, memory: dict) -> None:
        memory["exploiter"] = {
            "hands": 0,
            "opp_folds": 0,
            "showdowns": 0,
            "opp_raises_faced": 0,
        }

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        exp = memory.setdefault("exploiter", {
            "hands": 0, "opp_folds": 0, "showdowns": 0, "opp_raises_faced": 0
        })

        hands = max(1, exp["hands"])
        opp_fold_rate = exp["opp_folds"] / hands

        if obs.street == Street.PREFLOP:
            equity = preflop_hand_quality(obs.hole_cards)
        else:
            equity = hand_strength_sampled(obs.hole_cards, obs.board, num_samples=60, rng=self.rng)

        # Exploit high fold rate by stealing with half-pot raises
        if obs.to_call == 0:
            if opp_fold_rate > 0.40 and Action.RAISE_HALF in obs.legal_actions and hands >= 10:
                if self.rng.random() < 0.70:
                    return Action.RAISE_HALF
            if equity > 0.65 and Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Facing bet
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        if equity > pot_odds:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        exp = memory.setdefault("exploiter", {
            "hands": 0, "opp_folds": 0, "showdowns": 0, "opp_raises_faced": 0
        })
        exp["hands"] += 1
        if not result.went_to_showdown and result.winner == "me":
            # Opponent folded!
            exp["opp_folds"] += 1
        elif result.went_to_showdown:
            exp["showdowns"] += 1


class TellExploiterBot:
    """Exploits strength-revealing bet sizes:
    - Folds facing RAISE_POT unless holding nuts (> 0.88 equity)
    - Floats/calls facing RAISE_HALF
    - Attacks checks with pot-sized bets."""
    name = "TellExploiter"

    def __init__(self, seed: int = 111):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        equity = preflop_hand_quality(obs.hole_cards) if obs.street == Street.PREFLOP else hand_strength_sampled(obs.hole_cards, obs.board, num_samples=60, rng=self.rng)

        # Look at opponent's last action
        last_opp_action = None
        for a in reversed(obs.action_history):
            if not a.is_me:
                last_opp_action = a.action
                break

        if obs.to_call == 0:
            # Checked to: attack weakness
            if Action.RAISE_POT in obs.legal_actions and (equity > 0.40 or self.rng.random() < 0.60):
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions and equity > 0.45:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Facing bet
        if last_opp_action == Action.RAISE_POT:
            # Opponent tells us they have the nuts: fold unless we have monster
            if equity >= 0.88:
                return Action.CHECK_CALL
            return Action.FOLD

        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        if equity > pot_odds - 0.05:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class CheckAttackerBot:
    """Attacker targeting insufficiently protected checks:
    Whenever opponent checks, punishes by relentless pot betting."""
    name = "CheckAttacker"

    def __init__(self, seed: int = 222):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        equity = preflop_hand_quality(obs.hole_cards) if obs.street == Street.PREFLOP else hand_strength_sampled(obs.hole_cards, obs.board, num_samples=50, rng=self.rng)

        if obs.to_call == 0:
            # Relentlessly bet whenever checked to
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Facing a bet: call if decent equity
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        if equity > pot_odds + 0.02:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


class FrozenEquityBotAttacker:
    """Targeted response attacker built specifically against EquityBot_v1's decision logic:
    - EquityBot_v1 checks when equity < 0.50 -> Attacker bets POT to fold out 0.0 - 0.38 range
    - EquityBot_v1 bets POT when equity > 0.80 -> Attacker FOLDS immediately to save chips
    - EquityBot_v1 bets HALF when equity is 0.50 - 0.80 -> Attacker only calls with > 0.65 equity."""
    name = "FrozenEquityBotAttacker"

    def __init__(self, seed: int = 333):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        equity = preflop_hand_quality(obs.hole_cards) if obs.street == Street.PREFLOP else hand_strength_sampled(obs.hole_cards, obs.board, num_samples=60, rng=self.rng)

        last_opp_action = None
        for a in reversed(obs.action_history):
            if not a.is_me:
                last_opp_action = a.action
                break

        if obs.to_call == 0:
            # EquityBot checked: exploit by betting pot
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Facing a bet
        if last_opp_action == Action.RAISE_POT:
            # EquityBot only bets pot with monster hands (> 0.80): fold everything except nuts
            if equity >= 0.85:
                return Action.CHECK_CALL
            return Action.FOLD

        if last_opp_action == Action.RAISE_HALF:
            # EquityBot has 0.50 - 0.80: call only with good hands
            if equity >= 0.65:
                return Action.CHECK_CALL
            return Action.FOLD

        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)
        if equity > pot_odds:
            return Action.CHECK_CALL
        return Action.FOLD

    def on_hand_end(self, result: HandResult, memory: dict) -> None:
        pass


# Complete Opponent Registry
BASELINE_REGISTRY = {
    "check_fold": CheckFoldBot,
    "calling_station": CallingStationBot,
    "random": RandomBot,
    "always_raise": AlwaysRaiseBot,
    "guide_cheap_call": GuideCheapCallBot,
    "equity_call": EquityCallBot,
    "size_aware_equity": SizeAwareEquityBot,
    "action_conditioned_range": ActionConditionedRangeBot,
    "adaptive_exploiter": AdaptiveExploiterBot,
    "tell_exploiter": TellExploiterBot,
    "check_attacker": CheckAttackerBot,
    "frozen_equity_attacker": FrozenEquityBotAttacker,
}
