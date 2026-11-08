"""
opponents/adversarial.py - Targeted adversarial opponents designed to stress-test
the aggression model, street conditioning, and checking protection of RangeAware_v2.

Covers:
1. ThresholdAttackerBelow: Raise frequency ~58% (immediately below 62% threshold).
2. ThresholdAttackerAbove: Raise frequency ~72% (immediately above 62% threshold).
3. StreetInversionAttacker: High preflop aggression (90% raises) to inflate perceived
   maniac_factor, but 100% honest value on river (only raises with Cat >= 6).
4. RiverBluffAttacker: Low overall aggression (<12%) preflop/flop, but hyper-bluffs
   on turn and river when checked to.
5. ChameleonAttacker: Plays ultra-tight for first 25 hands (raise rate <10%), then
   phase-shifts into relentless aggression.
6. FoldBullyAttacker: Monitors opponent folds within the half; ramps up bluffs when
   opponent fold rate exceeds 35%.
7. CheckTrapAttacker: Protected checks: traps by checking 60% of boats and flushes,
   check-raising aggressive opponents.
8. SizingTellDisguiser: Reverses standard sizing tells: bets half-pot with nuts and
   pot with weak draws/air.
9. TrainedResponseBot: Optimized response agent with parameterized thresholds
   calibrated against frozen RangeAware_v2.
"""

from __future__ import annotations

import sys
import os
import random
from typing import Dict, Any, List

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import NUM_CARDS, category_of
from game import Action, Observation, Street
from runtime.features import omaha_best_score, preflop_hand_quality


class ThresholdAttackerBelow:
    """Raises ~58% of hands across all streets, hovering below the 62% maniac threshold."""
    def __init__(self, seed: int = 101):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if self.rng.random() < 0.58:
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
        return Action.CHECK_CALL if obs.to_call == 0 else (Action.CHECK_CALL if self.rng.random() < 0.6 else Action.FOLD)


class ThresholdAttackerAbove:
    """Raises ~72% of hands across all streets, hovering above the 62% maniac threshold."""
    def __init__(self, seed: int = 102):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if self.rng.random() < 0.72:
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
        return Action.CHECK_CALL if obs.to_call == 0 else (Action.CHECK_CALL if self.rng.random() < 0.5 else Action.FOLD)


class StreetInversionAttacker:
    """Preflop maniac (90% raises) to inflate perceived maniac_factor, but strictly value on River.
    
    Exploits bots that use a single global aggression rate to judge river re-raises.
    """
    def __init__(self, seed: int = 103):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        # Preflop & Flop: hyper-aggressive
        if obs.street in (Street.PREFLOP, Street.FLOP):
            if self.rng.random() < 0.90:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Turn: moderately aggressive
        if obs.street == Street.TURN:
            if self.rng.random() < 0.60:
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
            return Action.CHECK_CALL

        # River: 100% honest value only!
        score = omaha_best_score(obs.hole_cards, obs.board)
        cat = score >> 20
        if cat >= 6:  # Flush or better
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            return Action.CHECK_CALL
        elif cat >= 4:  # Trips / Boat
            if obs.to_call <= 8:
                return Action.CHECK_CALL
            return Action.FOLD
        else:
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD


class RiverBluffAttacker:
    """Passive preflop/flop (<12% raises), but attacks turn and river when checked to.
    
    Exploits bots that assume low global aggression implies river bets are always strong.
    """
    def __init__(self, seed: int = 104):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        # Preflop & Flop: limp/check/call
        if obs.street in (Street.PREFLOP, Street.FLOP):
            if obs.to_call == 0:
                return Action.CHECK_CALL
            if obs.to_call <= 4:
                return Action.CHECK_CALL
            return Action.FOLD

        # Turn & River: If checked to, bluff pot 75% of the time
        if obs.to_call == 0:
            if self.rng.random() < 0.75 and Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            return Action.CHECK_CALL

        # Facing bet on turn/river: call with medium+, fold weak
        score = omaha_best_score(obs.hole_cards, obs.board)
        cat = score >> 20
        if cat >= 3:
            return Action.CHECK_CALL
        return Action.FOLD


class ChameleonAttacker:
    """Ultra-tight for first 25 hands of half, then flips to hyper-aggressive bluffing.
    
    Exploits within-half memory that over-weights early observations.
    """
    def __init__(self, seed: int = 105):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        hand_idx = getattr(obs, "hand_index", 0)
        is_phase_1 = (hand_idx < 25)

        score = omaha_best_score(obs.hole_cards, obs.board) if obs.board else 0
        cat = score >> 20 if obs.board else 0

        if is_phase_1:
            # Ultra-tight rock
            if obs.street == Street.PREFLOP:
                q = preflop_hand_quality(obs.hole_cards)
                if q > 0.65:
                    return Action.RAISE_HALF if Action.RAISE_HALF in obs.legal_actions else Action.CHECK_CALL
                return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD
            else:
                if cat >= 4:
                    return Action.RAISE_POT if Action.RAISE_POT in obs.legal_actions else Action.CHECK_CALL
                return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD
        else:
            # Phase 2: Relentless bully
            if self.rng.random() < 0.75:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD


class FoldBullyAttacker:
    """Monitors opponent folds within the half. If opponent fold rate > 35%, increases aggression."""
    def __init__(self, seed: int = 106):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        # Track opponent folds in memory
        hand_idx = getattr(obs, "hand_index", 0)
        curr_hand = memory.get("_fb_hand", -1)
        if hand_idx != curr_hand:
            memory["_fb_hand"] = hand_idx
            memory["_fb_seen"] = set()

        seen = memory.setdefault("_fb_seen", set())
        for i, a in enumerate(obs.action_history):
            if not a.is_me and i not in seen:
                seen.add(i)
                memory["opp_actions"] = memory.get("opp_actions", 0) + 1
                if a.action == Action.FOLD:
                    memory["opp_folds"] = memory.get("opp_folds", 0) + 1

        opp_acts = memory.get("opp_actions", 1)
        opp_folds = memory.get("opp_folds", 0)
        opp_fold_rate = opp_folds / max(1, opp_acts)

        # If opponent folds a lot (> 35%), bully with 80% raises
        bluff_prob = 0.80 if opp_fold_rate > 0.35 else 0.40

        if self.rng.random() < bluff_prob:
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF

        return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD


class CheckTrapAttacker:
    """Protected checks: checks 60% of monster hands (Cat >= 5: Boats, Flushes) to trap and check-raise."""
    def __init__(self, seed: int = 107):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.street == Street.PREFLOP:
            q = preflop_hand_quality(obs.hole_cards)
            if q > 0.60 and self.rng.random() < 0.60:
                return Action.RAISE_HALF if Action.RAISE_HALF in obs.legal_actions else Action.CHECK_CALL
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD

        score = omaha_best_score(obs.hole_cards, obs.board)
        cat = score >> 20

        # Monster hand: slowplay check 60% of the time, check-raise if opponent bets
        if cat >= 5:
            if obs.to_call == 0:
                if self.rng.random() < 0.60:
                    return Action.CHECK_CALL  # trap check
                return Action.RAISE_POT if Action.RAISE_POT in obs.legal_actions else Action.CHECK_CALL
            else:
                # Spring the trap: re-raise pot!
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                return Action.CHECK_CALL

        # Medium hand: check/call small bets
        if cat >= 2:
            if obs.to_call <= 6:
                return Action.CHECK_CALL
            return Action.FOLD

        return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD


class SizingTellDisguiser:
    """Reverses standard bet sizing: bets half-pot with nuts (Cat >= 5) and pot with air/draws."""
    def __init__(self, seed: int = 108):
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.street == Street.PREFLOP:
            if self.rng.random() < 0.50:
                return Action.RAISE_HALF if Action.RAISE_HALF in obs.legal_actions else Action.CHECK_CALL
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD

        score = omaha_best_score(obs.hole_cards, obs.board)
        cat = score >> 20

        if cat >= 5:
            # Monster: bet half pot to induce calls
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL
        elif cat <= 1:
            # Air: bet pot to polarize and induce folds
            if self.rng.random() < 0.35 and Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD
        else:
            return Action.CHECK_CALL if obs.to_call <= 4 else Action.FOLD


class TrainedResponseBot:
    """Numerically optimized response policy against frozen RangeAware_v2.
    
    Parameters tuned via grid search:
    - preflop_open_thresh: 0.42
    - postflop_call_margin: 0.04
    - river_bluff_freq: 0.22
    - check_raise_freq: 0.35
    """
    def __init__(
        self,
        pf_open: float = 0.42,
        call_margin: float = 0.04,
        river_bluff: float = 0.22,
        check_raise: float = 0.35,
        seed: int = 109,
    ):
        self.pf_open = pf_open
        self.call_margin = call_margin
        self.river_bluff = river_bluff
        self.check_raise = check_raise
        self.rng = random.Random(seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.street == Street.PREFLOP:
            q = preflop_hand_quality(obs.hole_cards)
            if q > self.pf_open:
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
                return Action.CHECK_CALL
            return Action.CHECK_CALL if obs.to_call == 0 else Action.FOLD

        score = omaha_best_score(obs.hole_cards, obs.board)
        cat = score >> 20
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)

        # Facing bet
        if obs.to_call > 0:
            if cat >= 5 and self.rng.random() < self.check_raise:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
            if cat >= 3:
                return Action.CHECK_CALL
            if cat >= 1 and pot_odds < (0.25 + self.call_margin):
                return Action.CHECK_CALL
            return Action.FOLD

        # Unopened / checking
        if cat >= 4:
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            return Action.CHECK_CALL
        if cat >= 2:
            if Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.6:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # River air bluff
        if obs.street == Street.RIVER and self.rng.random() < self.river_bluff:
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT

        return Action.CHECK_CALL


ADVERSARIAL_REGISTRY = {
    "threshold_attacker_below": ThresholdAttackerBelow,
    "threshold_attacker_above": ThresholdAttackerAbove,
    "street_inversion_attacker": StreetInversionAttacker,
    "river_bluff_attacker": RiverBluffAttacker,
    "chameleon_attacker": ChameleonAttacker,
    "fold_bully_attacker": FoldBullyAttacker,
    "check_trap_attacker": CheckTrapAttacker,
    "sizing_tell_disguiser": SizingTellDisguiser,
    "trained_response_bot": TrainedResponseBot,
}

