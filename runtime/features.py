"""
runtime/features.py - Feature extraction from Observation for policy decisions.

Extracts compact numeric features from the game observation suitable for
strategy lookup and decision-making. All features are computable from
public information available to the acting player.

Feature schema version: 1
"""

from __future__ import annotations

import sys
import os

# Add starter to path for evaluator access
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "starter"))

from itertools import combinations
from typing import Sequence

from evaluator import (
    NUM_CARDS, card_rank, card_suit, get_table, omaha_score,
    category_of, ACE, STRAIGHT_FLUSH, FLUSH, FOUR_OF_A_KIND,
    FULL_HOUSE, THREE_OF_A_KIND, STRAIGHT, TWO_PAIR, ONE_PAIR, HIGH_CARD,
)
from game import Action, Observation, Street, STARTING_STACK, BIG_BLIND

# 10 ways to pick 2 of 5 hole cards
_PAIRS = tuple(combinations(range(5), 2))
# 10 ways to pick 3 of 5 board cards
_TRIPLES = tuple(combinations(range(5), 3))

FEATURE_SCHEMA_VERSION = 1


def hand_strength(hole: Sequence[int], board: Sequence[int]) -> float:
    """Estimate hand strength as fraction of opponent hands we beat.

    Enumerates all possible 5-card opponent hands from remaining cards,
    using the Omaha 2+3 rule. Returns value in [0, 1].
    """
    if len(board) < 3:
        return 0.5  # No board yet, can't evaluate

    my_score = omaha_score(list(hole), list(board))

    # Cards that are taken (in our hand or on the board)
    used = set(hole) | set(board)
    remaining = [c for c in range(NUM_CARDS) if c not in used]

    # Sample opponent hands: enumerate all C(remaining, 5) hands
    # For 36-card deck minus 10 visible = 26 remaining
    # C(26, 5) = 65,780 opponent hands -- feasible for post-flop
    wins = 0
    ties = 0
    total = 0

    table = get_table()

    for combo in combinations(remaining, 5):
        opp_hole = combo
        # Compute opponent's best Omaha score using exactly 2 hole + 3 board
        opp_best = 0
        opp_hole_bits = [1 << c for c in opp_hole]
        board_bits = [1 << c for c in board]

        board_masks = [board_bits[i] | board_bits[j] | board_bits[k]
                       for i, j, k in _TRIPLES if k < len(board)]

        for i, j in _PAIRS:
            hm = opp_hole_bits[i] | opp_hole_bits[j]
            for bm in board_masks:
                score = table.get(hm | bm, 0)
                if score > opp_best:
                    opp_best = score

        if my_score > opp_best:
            wins += 1
        elif my_score == opp_best:
            ties += 1
        total += 1

    if total == 0:
        return 0.5
    return (wins + 0.5 * ties) / total


def precompute_board_masks(board: Sequence[int]) -> tuple[int, ...]:
    """Precompute 3-card board bitmasks for fast Omaha evaluation."""
    b_bits = [1 << c for c in board]
    combos = combinations(range(len(board)), 3)
    return tuple(b_bits[i] | b_bits[j] | b_bits[k] for i, j, k in combos)


def omaha_score_fast(hole: Sequence[int], board_masks: Sequence[int], table: dict) -> int:
    """Fast score using precomputed board masks and direct bit-shifts."""
    hb0, hb1, hb2, hb3, hb4 = 1 << hole[0], 1 << hole[1], 1 << hole[2], 1 << hole[3], 1 << hole[4]
    h_masks = (
        hb0 | hb1, hb0 | hb2, hb0 | hb3, hb0 | hb4,
        hb1 | hb2, hb1 | hb3, hb1 | hb4,
        hb2 | hb3, hb2 | hb4,
        hb3 | hb4,
    )
    best = 0
    for hm in h_masks:
        for bm in board_masks:
            score = table[hm | bm]
            if score > best:
                best = score
    return best


def omaha_best_score(hole: Sequence[int], board: Sequence[int]) -> int:
    """Best score using EXACTLY 2 of 5 hole cards and EXACTLY 3 board cards.

    Works for any board length >= 3 (flop=3, turn=4, river=5).
    """
    if len(hole) != 5 or len(board) < 3:
        raise ValueError("Need 5 hole cards and at least 3 board cards")
    table = get_table()
    board_masks = precompute_board_masks(board)
    return omaha_score_fast(hole, board_masks, table)


def hand_strength_sampled(hole: Sequence[int], board: Sequence[int],
                          num_samples: int = 100, rng=None) -> float:
    """Monte Carlo hand strength estimate using random opponent hands.

    Supports flop (3 board), turn (4 board), and river (5 board).
    Returns value in [0, 1].
    """
    import random as _random
    if rng is None:
        rng = _random

    if len(board) < 3:
        return 0.5

    my_score = omaha_best_score(hole, board)
    used = set(hole) | set(board)
    remaining = [c for c in range(NUM_CARDS) if c not in used]

    if len(remaining) < 5:
        return 0.5

    table = get_table()
    board_bits = [1 << c for c in board]
    board_combos = tuple(combinations(range(len(board)), 3))
    board_masks = [board_bits[i] | board_bits[j] | board_bits[k] for i, j, k in board_combos]

    wins = 0
    ties = 0

    for _ in range(num_samples):
        opp_hole = rng.sample(remaining, 5)
        opp_hole_bits = [1 << c for c in opp_hole]
        opp_hole_masks = [opp_hole_bits[i] | opp_hole_bits[j] for i, j in _PAIRS]

        opp_best = 0
        for hm in opp_hole_masks:
            for bm in board_masks:
                score = table[hm | bm]
                if score > opp_best:
                    opp_best = score

        if my_score > opp_best:
            wins += 1
        elif my_score == opp_best:
            ties += 1

    return (wins + 0.5 * ties) / num_samples


def preflop_hand_quality(hole: Sequence[int]) -> float:
    """Estimate preflop hand quality based on card properties.

    Considers: pairs, high cards, suitedness, connectedness.
    Returns value in [0, 1] where 1 is best possible hand.
    """
    ranks = [card_rank(c) for c in hole]
    suits = [card_suit(c) for c in hole]

    score = 0.0

    # High card value (weighted by rank)
    max_rank = max(ranks)
    score += max_rank / (ACE * 2)  # up to 0.5

    # Pairs and trips
    from collections import Counter
    rank_counts = Counter(ranks)
    max_count = max(rank_counts.values())
    if max_count >= 2:
        pair_rank = max(r for r, c in rank_counts.items() if c >= 2)
        score += 0.15 * (pair_rank / ACE)
    if max_count >= 3:
        score += 0.1

    # Suitedness - count max cards of same suit
    suit_counts = Counter(suits)
    max_suited = max(suit_counts.values())
    if max_suited >= 3:
        score += 0.15
    elif max_suited >= 2:
        score += 0.05

    # Connectedness - count cards that form potential straights
    unique_ranks = sorted(set(ranks))
    max_connected = 1
    current = 1
    for i in range(1, len(unique_ranks)):
        if unique_ranks[i] - unique_ranks[i-1] <= 2:  # gaps of 1 or 2
            current += 1
            max_connected = max(max_connected, current)
        else:
            current = 1
    if max_connected >= 4:
        score += 0.1
    elif max_connected >= 3:
        score += 0.05

    return min(1.0, score)


def extract_features(obs: Observation) -> dict:
    """Extract feature dictionary from observation for policy decisions.

    Returns a dict with named features for interpretability and flexibility.
    """
    features = {}

    # Position
    features["is_button"] = 1.0 if obs.is_button else 0.0

    # Street
    features["street"] = float(obs.street)

    # Stack and pot geometry
    features["pot_frac_stack"] = obs.pot / max(1, STARTING_STACK * 2)
    features["my_stack_frac"] = obs.my_stack / STARTING_STACK
    features["opp_stack_frac"] = obs.opp_stack / STARTING_STACK
    features["to_call_frac_pot"] = obs.to_call / max(1, obs.pot)
    features["spr"] = obs.my_stack / max(1, obs.pot)  # stack-to-pot ratio

    # Bet sizing info
    features["raises_this_street"] = float(obs.raises_this_street)
    can_raise = Action.RAISE_HALF in obs.legal_actions
    features["can_raise"] = 1.0 if can_raise else 0.0

    # Hand quality
    if obs.street == Street.PREFLOP:
        features["hand_quality"] = preflop_hand_quality(obs.hole_cards)
        features["hand_strength"] = features["hand_quality"]
    else:
        # Use sampled hand strength for speed
        features["hand_quality"] = preflop_hand_quality(obs.hole_cards)
        features["hand_strength"] = hand_strength_sampled(
            obs.hole_cards, obs.board, num_samples=150
        )

    # Hand category (post-flop only)
    if len(obs.board) >= 3:
        my_score = omaha_best_score(obs.hole_cards, obs.board)
        features["hand_category"] = float(category_of(my_score))
    else:
        features["hand_category"] = 0.0

    # Action history summary
    my_raises = sum(1 for a in obs.action_history if a.is_me and a.action in (Action.RAISE_HALF, Action.RAISE_POT))
    opp_raises = sum(1 for a in obs.action_history if not a.is_me and a.action in (Action.RAISE_HALF, Action.RAISE_POT))
    features["my_raises_total"] = float(my_raises)
    features["opp_raises_total"] = float(opp_raises)

    # Free check opportunity
    features["is_free_check"] = 1.0 if obs.to_call == 0 else 0.0

    return features

