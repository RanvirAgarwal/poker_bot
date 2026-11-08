"""
runtime/ablations.py - Isolated ablation variants of the Range-Aware architecture.

Isolates:
1. Ablation_EquityOnly: Pure uniform sampling (EquityBot_v1 baseline behavior).
2. Ablation_RangeOnly: Action conditioning with static prior (no memory adaptation, no continuation filter).
3. Ablation_RangeAndAdapt: Action conditioning + within-half Bayesian aggression adaptation (no continuation filter).
4. Ablation_Complete: Complete RangeAware_v2 (Action conditioning + Adaptation + Continuation filter).

All base bet sizes, thresholds, positional adjustments, and RNG seeds are strictly identical.

Changelog (F4 fix):
- _update_memory_opp_stats returns Tuple[float, float]; was assigned to single variable.
- _compute_action_conditioned_equity expects (pf_raise_rate, post_raise_rate) kwargs; was called
  with wrong kwarg name opp_raise_rate.
- EquityOnly preflop now uses preflop_hand_quality (not hand_strength_sampled which returns 0.5).
- Experiments re-raise unexpected exceptions instead of silently substituting fallback strategy.
"""

from __future__ import annotations

import random
from typing import Sequence, Tuple, List, Dict
from evaluator import NUM_CARDS, category_of
from game import Action, Observation, Street
from runtime.features import omaha_best_score, preflop_hand_quality
from runtime.range_aware_policy import RangeAwarePolicy


class AblationPolicy(RangeAwarePolicy):
    """Parametric ablation controller for controlled isolation experiments."""

    def __init__(
        self,
        enable_range_conditioning: bool = True,
        enable_aggression_adaptation: bool = True,
        enable_continuation_filter: bool = True,
        aggression: float = 1.0,
        seed: int = 42,
    ):
        super().__init__(aggression=aggression, seed=seed)
        self.enable_range_conditioning = enable_range_conditioning
        self.enable_aggression_adaptation = enable_aggression_adaptation
        self.enable_continuation_filter = enable_continuation_filter

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        if obs.to_call == 0 and Action.RAISE_HALF not in obs.legal_actions:
            return Action.CHECK_CALL

        is_btn = obs.is_button
        street = obs.street
        pot_odds = obs.to_call / max(1, obs.pot + obs.to_call)

        # 1. Opponent aggression rate
        # _update_memory_opp_stats returns Tuple[float, float] — unpack both values (F4 fix)
        if self.enable_aggression_adaptation:
            pf_rate, post_rate = self._update_memory_opp_stats(obs, memory)
        else:
            pf_rate, post_rate = 0.20, 0.15  # static prior

        # 2. Equity estimation
        if not self.enable_range_conditioning:
            # Uniform sampling with preflop hand quality (EquityBot_v1 behavior)
            # Note: hand_strength_sampled returns 0.5 preflop (no board); use preflop_hand_quality instead.
            if obs.street == Street.PREFLOP:
                eq_current = preflop_hand_quality(obs.hole_cards)
            else:
                from runtime.features import hand_strength_sampled
                eq_current = hand_strength_sampled(obs.hole_cards, obs.board, num_samples=80, rng=self.rng)
            eq_continue = eq_current
        else:
            # F4 fix: pass correct kwarg names pf_raise_rate and post_raise_rate
            eq_current, eq_continue_calc = self._compute_action_conditioned_equity(
                obs, pf_raise_rate=pf_rate, post_raise_rate=post_rate
            )
            eq_continue = eq_continue_calc if self.enable_continuation_filter else eq_current

        if street == Street.PREFLOP:
            return self._preflop_action(obs, eq_current, is_btn, pot_odds)
        else:
            return self._postflop_action(obs, eq_current, eq_continue, is_btn, pot_odds)
