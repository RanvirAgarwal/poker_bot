"""
runtime/range_aware_policy.py - RangeAware_v2 Policy Candidate.

Implements compact action-conditioned opponent-range modeling:
- Conditions opponent hand distribution on observed betting actions, street, and sizes.
- Incorporates card removal strictly from observable cards (hole + board).
- Models bluff uncertainty: never assumes 100% honesty; retains smooth likelihood weights.
- Distinguishes equity against current betting range from equity against continuation range.
- Keeps base sizing and thresholds identical to EquityBot_v1 to cleanly isolate range-conditioning benefit.
"""

from __future__ import annotations

import sys
import os
import random
import time
from typing import Sequence, Tuple, List, Dict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import NUM_CARDS, category_of, get_table
from game import Action, Observation, Street
from runtime.features import (
    omaha_best_score,
    omaha_score_fast,
    precompute_board_masks,
    preflop_hand_quality,
)


class RangeAwarePolicy:
    """Action-Conditioned Range Policy (RangeAware_v2)."""

    def __init__(self, aggression: float = 1.0, seed: int = 42, use_continuation_filter: bool = True, num_samples: int = 30):
        self.aggression = aggression
        self.rng = random.Random(seed)
        self.use_continuation_filter = use_continuation_filter
        self.num_samples = num_samples

    def _update_memory_opp_stats(self, obs: Observation, memory: dict) -> Tuple[float, float]:
        """Update and return (preflop_raise_rate, postflop_raise_rate) from memory.
        
        Uses Beta priors:
        - Preflop: Beta(2.5, 7.5) (prior mean 25% raise frequency)
        - Postflop: Beta(1.5, 8.5) (prior mean 15% raise frequency)
        Separate street tracking prevents preflop aggression from distorting river ranges.
        """
        if not isinstance(memory, dict):
            return 0.25, 0.15

        # Track hand number to avoid double counting actions in the same hand
        hand_idx = getattr(obs, "hand_index", 0)
        current_hand = memory.get("_current_hand", -1)
        if hand_idx != current_hand:
            memory["_current_hand"] = hand_idx
            memory["_seen_action_indices"] = set()

        seen_indices = memory.setdefault("_seen_action_indices", set())
        pf_acts = memory.setdefault("pf_opp_actions", 0)
        pf_raises = memory.setdefault("pf_opp_raises", 0)
        post_acts = memory.setdefault("post_opp_actions", 0)
        post_raises = memory.setdefault("post_opp_raises", 0)

        for i, a in enumerate(obs.action_history):
            if not a.is_me and i not in seen_indices:
                seen_indices.add(i)
                is_raise = (a.action in (Action.RAISE_HALF, Action.RAISE_POT))
                if a.street == Street.PREFLOP:
                    pf_acts += 1
                    if is_raise:
                        pf_raises += 1
                else:
                    post_acts += 1
                    if is_raise:
                        post_raises += 1

        memory["pf_opp_actions"] = pf_acts
        memory["pf_opp_raises"] = pf_raises
        memory["post_opp_actions"] = post_acts
        memory["post_opp_raises"] = post_raises

        pf_rate = (pf_raises + 2.5) / (pf_acts + 10.0)
        post_rate = (post_raises + 1.5) / (post_acts + 10.0)
        return pf_rate, post_rate

    def _compute_action_conditioned_equity(
        self,
        obs: Observation,
        pf_raise_rate: float = 0.25,
        post_raise_rate: float = 0.15,
        num_samples: int = 80,
    ) -> Tuple[float, float]:
        """Estimate equity against opponent's current range and continuation range.

        Conditions on observed betting actions, smoothly adapted by street-specific aggression.
        Returns (equity_vs_current_range, equity_vs_continuation_range).
        """
        hole = obs.hole_cards
        board = obs.board
        used = set(hole) | set(board)
        remaining = [c for c in range(NUM_CARDS) if c not in used]

        # Analyze observable opponent aggression
        opp_pf_raises = sum(1 for a in obs.action_history if not a.is_me and a.street == Street.PREFLOP and a.action in (Action.RAISE_HALF, Action.RAISE_POT))
        opp_re_raised_here = obs.raises_this_street >= 2

        # Street-specific maniac factors
        pf_maniac_factor = min(1.0, max(0.0, (pf_raise_rate - 0.25) / 0.35))
        post_maniac_factor = min(1.0, max(0.0, (post_raise_rate - 0.18) / 0.35))

        # Fast path for preflop
        if obs.street == Street.PREFLOP:
            raw_q = preflop_hand_quality(hole)
            if opp_pf_raises >= 2:
                penalty = (1.0 - pf_maniac_factor) * 0.12 + pf_maniac_factor * 0.02
                adj_q = max(0.0, raw_q - penalty)
            elif opp_pf_raises == 1:
                penalty = (1.0 - pf_maniac_factor) * 0.05 + pf_maniac_factor * 0.01
                adj_q = max(0.0, raw_q - penalty)
            else:
                adj_q = raw_q
            return adj_q, adj_q

        # Postflop: Sample candidate opponent hands and calculate likelihood weights
        table = get_table()
        board_masks = precompute_board_masks(board)
        my_score = omaha_score_fast(hole, board_masks, table)

        candidate_weights = []
        candidate_scores = []

        # Generate candidates
        for _ in range(num_samples):
            opp_hole = self.rng.sample(remaining, 5)
            score = omaha_score_fast(opp_hole, board_masks, table)
            cat = score >> 20
            pf_q = preflop_hand_quality(opp_hole)

            # Likelihood weighting:
            # 1. Preflop aggression weight
            w = 1.0
            if opp_pf_raises >= 1:
                pf_w = (pf_q + 0.15)
                w *= ((1.0 - pf_maniac_factor) * pf_w + pf_maniac_factor * 1.0)

            # 2. Postflop action weight: conditioned by postflop aggression!
            if opp_re_raised_here:
                if cat >= 6:      # Flush or better
                    w_action = 3.0
                elif cat >= 4:    # Trips or Full House
                    w_action = 2.0
                elif cat >= 2:    # Two Pair
                    w_action = 0.5
                else:             # One Pair or High Card (bluff)
                    w_action = 0.12
            elif obs.to_call > 0:
                if cat >= 4:
                    w_action = 1.8
                elif cat >= 2:
                    w_action = 1.2
                else:
                    w_action = 0.35
            else:
                if cat >= 6:
                    w_action = 0.40
                elif cat <= 2:
                    w_action = 1.30
                else:
                    w_action = 1.0

            # Blend with uniform weight based on postflop aggression only
            w *= ((1.0 - post_maniac_factor) * w_action + post_maniac_factor * 1.0)

            candidate_weights.append(max(0.01, w))
            candidate_scores.append(score)

        # Compute weighted equity vs current range
        total_w = sum(candidate_weights)
        wins = 0.0
        ties = 0.0

        # Continuation range
        cont_w_total = 0.0
        cont_wins = 0.0
        cont_ties = 0.0

        for sc, w in zip(candidate_scores, candidate_weights):
            if my_score > sc:
                wins += w
            elif my_score == sc:
                ties += w

            cat = sc >> 20
            base_cont = 0.90 if cat >= 4 else (0.60 if cat >= 2 else 0.10)
            cont_prob = (1.0 - post_maniac_factor) * base_cont + post_maniac_factor * 0.85
            cont_w = w * cont_prob
            cont_w_total += cont_w
            if my_score > sc:
                cont_wins += cont_w
            elif my_score == sc:
                cont_ties += cont_w

        eq_current = (wins + 0.5 * ties) / total_w if total_w > 0 else 0.5
        if self.use_continuation_filter:
            eq_continue = (cont_wins + 0.5 * cont_ties) / cont_w_total if cont_w_total > 0 else eq_current
        else:
            eq_continue = eq_current

        return eq_current, eq_continue

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.to_call == 0 and Action.RAISE_HALF not in obs.legal_actions:
            return Action.CHECK_CALL

        t0 = time.perf_counter()
        is_btn = obs.is_button
        street = obs.street
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)

        # Update street-specific opponent statistics in memory
        pf_rate, post_rate = self._update_memory_opp_stats(obs, memory)

        # Dynamic time budgeting to guarantee 0 bank exhaustion
        eff_samples = self.num_samples
        if isinstance(memory, dict):
            spent = memory.get("_spent_bank", 0.0)
            if spent > 6.0:
                eff_samples = min(eff_samples, 10)
            elif spent > 4.5:
                eff_samples = min(eff_samples, 18)
            elif spent > 3.0:
                eff_samples = min(eff_samples, 24)

        # Get range-conditioned equity
        eq_current, eq_continue = self._compute_action_conditioned_equity(
            obs, pf_raise_rate=pf_rate, post_raise_rate=post_rate, num_samples=eff_samples
        )

        if street == Street.PREFLOP:
            act = self._preflop_action(obs, eq_current, is_btn, pot_odds)
        else:
            act = self._postflop_action(obs, eq_current, eq_continue, is_btn, pot_odds)

        if isinstance(memory, dict):
            elapsed = time.perf_counter() - t0
            memory["_spent_bank"] = memory.get("_spent_bank", 0.0) + max(0.0, elapsed - 0.0008)

        return act

    def _preflop_action(self, obs: Observation, strength: float,
                        is_btn: bool, pot_odds: float) -> Action:
        pos_boost = 0.05 if is_btn else 0.0
        adj_strength = strength + pos_boost

        if obs.to_call > 0:
            if adj_strength > 0.65 * self.aggression:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
                return Action.CHECK_CALL

            if adj_strength > 0.35 * self.aggression:
                if pot_odds < adj_strength * 0.8:
                    return Action.CHECK_CALL
                if self.rng.random() < 0.3:
                    return Action.CHECK_CALL
                return Action.FOLD

            if self.rng.random() < 0.08:
                if Action.RAISE_POT in obs.legal_actions:
                    return Action.RAISE_POT
                return Action.CHECK_CALL
            return Action.FOLD

        # Unopened / checking
        if adj_strength > 0.50 * self.aggression:
            if Action.RAISE_POT in obs.legal_actions:
                if adj_strength > 0.65:
                    return Action.RAISE_POT
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        if adj_strength > 0.30:
            if is_btn and Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.5:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        return Action.CHECK_CALL

    def _postflop_action(
        self,
        obs: Observation,
        eq_current: float,
        eq_continue: float,
        is_btn: bool,
        pot_odds: float,
    ) -> Action:
        pos_boost = 0.03 if is_btn else 0.0
        adj_strength = eq_current + pos_boost
        adj_cont = eq_continue + pos_boost
        spr = obs.my_stack / max(1, obs.pot)

        if obs.to_call > 0:
            # Facing bet or re-raise
            # If facing a heavy re-raise on turn or river, require strong continuation equity
            if obs.raises_this_street >= 2:
                # Re-raise protection: only raise nuts, fold marginal hands
                if adj_strength > 0.80 and adj_cont > 0.70:
                    if Action.RAISE_POT in obs.legal_actions:
                        return Action.RAISE_POT
                    return Action.CHECK_CALL
                if adj_strength > pot_odds + 0.08:
                    return Action.CHECK_CALL
                return Action.FOLD

            # Normal single bet faced
            if adj_strength > 0.75 and adj_cont > 0.60:
                if Action.RAISE_POT in obs.legal_actions:
                    if adj_strength > 0.85 or spr < 2:
                        return Action.RAISE_POT
                    return Action.RAISE_HALF
                return Action.CHECK_CALL

            if adj_strength > 0.55:
                if adj_strength > 0.65 and adj_cont > 0.55 and Action.RAISE_HALF in obs.legal_actions:
                    if self.rng.random() < 0.3:
                        return Action.RAISE_HALF
                return Action.CHECK_CALL

            if adj_strength > pot_odds + 0.05:
                return Action.CHECK_CALL

            # Cheap call on river (e.g. <= 4 chips into large pot)
            if obs.street == Street.RIVER and obs.to_call <= 4 and adj_strength > 0.25:
                if self.rng.random() < 0.2:
                    return Action.CHECK_CALL

            return Action.FOLD

        # No bet to call (checking node)
        # 1. Protected checking: when OOP on flop/turn with monster hand, trap-check 20% to check-raise
        if not is_btn and obs.street in (Street.FLOP, Street.TURN) and adj_strength > 0.75:
            if self.rng.random() < 0.20:
                return Action.CHECK_CALL

        if adj_strength > 0.65 and adj_cont > 0.50:
            if Action.RAISE_POT in obs.legal_actions and Action.RAISE_HALF in obs.legal_actions:
                # Mixed sizing: mix pot (65%) and half-pot (35%) to eliminate deterministic sizing tells
                return Action.RAISE_POT if self.rng.random() < 0.65 else Action.RAISE_HALF
            if Action.RAISE_POT in obs.legal_actions:
                return Action.RAISE_POT
            if Action.RAISE_HALF in obs.legal_actions:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        if adj_strength > 0.50 and adj_cont > 0.42:
            if Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.50:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        if adj_strength > 0.35:
            if Action.RAISE_HALF in obs.legal_actions and self.rng.random() < 0.15:
                return Action.RAISE_HALF
            return Action.CHECK_CALL

        # Mixed bluffing: mix half and pot
        if adj_strength < 0.20:
            if self.rng.random() < 0.06:
                if Action.RAISE_POT in obs.legal_actions and self.rng.random() < 0.50:
                    return Action.RAISE_POT
                if Action.RAISE_HALF in obs.legal_actions:
                    return Action.RAISE_HALF
        return Action.CHECK_CALL
