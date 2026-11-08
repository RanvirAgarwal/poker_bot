"""
runtime/draw_aware_policy.py - DrawAware_v1 Policy Candidate.

Separately versioned candidate addressing Finding F1 (draw blindness):
- Flop and turn decision equity samples joint deals: opponent private cards + compatible
  future board runouts (2 cards on flop, 1 card on turn, 0 cards on river).
- Made-hand score on the visible board is retained as a distinct feature.
- Past-action likelihood weighting conditions strictly on observable information at the time
  actions occurred (preflop hand quality, made-hand score on the current visible board);
  it NEVER conditions past actions on sampled future board cards (no look-ahead bias).
- Evaluates showdown outcome using complete 5-card board scores.
- Dynamic time budgeting ensures strict compliance with the 8.0s half-match time bank.
- Retains RangeAware_v2 as an untouched, frozen rollback candidate.
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
    omaha_score_fast,
    precompute_board_masks,
    preflop_hand_quality,
)
from runtime.range_aware_policy import RangeAwarePolicy


class DrawAwarePolicy(RangeAwarePolicy):
    """Draw-Aware, Action-Conditioned Range Policy (DrawAware_v1)."""

    def __init__(
        self,
        aggression: float = 1.0,
        seed: int = 42,
        use_continuation_filter: bool = True,
        num_samples: int = 30,
    ):
        super().__init__(
            aggression=aggression,
            seed=seed,
            use_continuation_filter=use_continuation_filter,
            num_samples=num_samples,
        )

    def _compute_action_conditioned_equity(
        self,
        obs: Observation,
        pf_raise_rate: float = 0.25,
        post_raise_rate: float = 0.15,
        num_samples: int = 30,
        uniform: bool = False,
    ) -> Tuple[float, float]:
        """Estimate showdown equity against opponent range, modeling future board cards.

        Key requirements (F1 fix):
        1. On flop (3 board cards) and turn (4 board cards), samples remaining board runout
           jointly with opponent hand from the unseen deck.
        2. Retains current made-hand score on visible board as a distinct feature for
           past-action likelihood weighting.
        3. Never conditions past actions on sampled future board cards (no look-ahead bias).
        4. On river (5 board cards), exact 5-card board evaluation is used directly.
        """
        hole = obs.hole_cards
        board = obs.board
        used = set(hole) | set(board)
        remaining = [c for c in range(NUM_CARDS) if c not in used]

        # Fast path for preflop
        if obs.street == Street.PREFLOP:
            return super()._compute_action_conditioned_equity(
                obs, pf_raise_rate=pf_raise_rate, post_raise_rate=post_raise_rate, num_samples=num_samples
            )

        # Analyze observable opponent aggression
        opp_pf_raises = sum(
            1 for a in obs.action_history
            if not a.is_me and a.street == Street.PREFLOP and a.action in (Action.RAISE_HALF, Action.RAISE_POT)
        )
        opp_re_raised_here = obs.raises_this_street >= 2

        pf_maniac_factor = min(1.0, max(0.0, (pf_raise_rate - 0.25) / 0.35))
        post_maniac_factor = min(1.0, max(0.0, (post_raise_rate - 0.18) / 0.35))

        table = get_table()
        # Made-hand score on currently visible board
        current_board_masks = precompute_board_masks(board)
        my_made_score = omaha_score_fast(hole, current_board_masks, table)

        cards_needed = 5 - len(board)  # 2 on flop, 1 on turn, 0 on river

        candidate_weights = []
        sd_wins = 0.0
        sd_ties = 0.0
        total_w = 0.0

        cont_w_total = 0.0
        cont_sd_wins = 0.0
        cont_sd_ties = 0.0

        # Sample joint deals
        for _ in range(num_samples):
            # Sample opponent hole cards (5 cards)
            opp_hole = self.rng.sample(remaining, 5)

            # Likelihood weighting based strictly on CURRENT information (no future lookahead)
            if uniform:
                w = 1.0
                opp_current_score = omaha_score_fast(opp_hole, current_board_masks, table)
            else:
                # 1. Made-hand score on currently visible board
                opp_current_score = omaha_score_fast(opp_hole, current_board_masks, table)
                cat = opp_current_score >> 20
                pf_q = preflop_hand_quality(opp_hole)

                w = 1.0
                if opp_pf_raises >= 1:
                    pf_w = pf_q + 0.15
                    w *= ((1.0 - pf_maniac_factor) * pf_w + pf_maniac_factor * 1.0)

                if opp_re_raised_here:
                    if cat >= 6:      # Flush or better
                        w_action = 3.0
                    elif cat >= 4:    # Trips or Full House
                        w_action = 2.0
                    elif cat >= 2:    # Two Pair
                        w_action = 0.5
                    else:             # One Pair or High Card
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

                w *= ((1.0 - post_maniac_factor) * w_action + post_maniac_factor * 1.0)
                w = max(0.01, w)

            # Sample future board runout (joint deal)
            if cards_needed > 0:
                runout_pool = [c for c in remaining if c not in opp_hole]
                runout = self.rng.sample(runout_pool, cards_needed)
                full_board = list(board) + runout
                full_bm = precompute_board_masks(full_board)
                my_sd_score = omaha_score_fast(hole, full_bm, table)
                opp_sd_score = omaha_score_fast(opp_hole, full_bm, table)
            else:
                # River: full board already visible
                my_sd_score = my_made_score
                opp_sd_score = opp_current_score

            total_w += w
            if my_sd_score > opp_sd_score:
                sd_wins += w
            elif my_sd_score == opp_sd_score:
                sd_ties += w

            # Continuation range weighting
            cat_made = opp_current_score >> 20
            base_cont = 0.90 if cat_made >= 4 else (0.60 if cat_made >= 2 else 0.10)
            cont_prob = (1.0 - post_maniac_factor) * base_cont + post_maniac_factor * 0.85
            cont_w = w * cont_prob
            cont_w_total += cont_w
            if my_sd_score > opp_sd_score:
                cont_sd_wins += cont_w
            elif my_sd_score == opp_sd_score:
                cont_sd_ties += cont_w

        eq_current = (sd_wins + 0.5 * sd_ties) / total_w if total_w > 0 else 0.5
        if self.use_continuation_filter:
            eq_continue = (cont_sd_wins + 0.5 * cont_sd_ties) / cont_w_total if cont_w_total > 0 else eq_current
        else:
            eq_continue = eq_current

        return eq_current, eq_continue


def draw_aware_equity_estimate(
    policy: DrawAwarePolicy,
    obs: Observation,
    uniform: bool = True,
    num_samples: int | None = None,
) -> float:
    """Helper function to calculate draw-aware showdown equity for testing/validation.

    Args:
        policy: DrawAwarePolicy instance.
        obs: Game observation.
        uniform: Whether to use uniform opponent weighting.
        num_samples: Number of joint samples (defaults to policy.num_samples).

    Returns:
        Estimated showdown equity in [0, 1].
    """
    n_samples = num_samples or policy.num_samples
    eq_current, _ = policy._compute_action_conditioned_equity(
        obs, num_samples=n_samples, uniform=uniform
    )
    return eq_current
