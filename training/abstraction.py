"""
training/abstraction.py - Card abstraction and information set representation.

Maps raw hole cards and game states into discrete information set keys (buckets)
for External-Sampling Monte Carlo Counterfactual Regret Minimization (ES-MCCFR).
"""

from __future__ import annotations

import sys
import os
from typing import Sequence

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from evaluator import NUM_CARDS, card_rank, card_suit, ACE
from game import Street, Observation
from runtime.features import preflop_hand_quality, omaha_best_score

NUM_PREFLOP_BUCKETS = 10
NUM_POSTFLOP_BUCKETS = 10


def get_preflop_bucket(hole: Sequence[int], num_buckets: int = NUM_PREFLOP_BUCKETS) -> int:
    """Bucket preflop hole cards into discrete quality bins [0, num_buckets - 1]."""
    quality = preflop_hand_quality(hole)
    bucket = int(quality * num_buckets)
    return min(num_buckets - 1, max(0, bucket))


def get_postflop_bucket(hole: Sequence[int], board: Sequence[int],
                        num_buckets: int = NUM_POSTFLOP_BUCKETS) -> int:
    """Bucket postflop hand based on relative hand score rank."""
    score = omaha_best_score(hole, board)
    # omaha score bits: category in bits 20+ (0 to 8)
    cat = score >> 20
    # Map category (0..8) and tie-breaker to [0, num_buckets - 1]
    norm = min(1.0, (cat * (1 << 20) + (score & 0xFFFFF)) / (9 * (1 << 20)))
    bucket = int(norm * num_buckets)
    return min(num_buckets - 1, max(0, bucket))


def make_infoset_key(
    street: Street,
    bucket: int,
    betting_history: str,
) -> str:
    """Construct a compact string identifier for an information set.

    Example: 'P:b7:C_R' -> Preflop, bucket 7, call then raise.
    """
    prefix = {
        Street.PREFLOP: "P",
        Street.FLOP: "F",
        Street.TURN: "T",
        Street.RIVER: "R",
    }[street]
    return f"{prefix}:{bucket}:{betting_history}"

