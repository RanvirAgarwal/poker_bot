"""
runtime/cfr_policy.py - Policy that queries a trained CFR strategy table.

Falls back gracefully to HeuristicPolicy if an information set was not
visited during offline training.
"""

from __future__ import annotations

import sys
import os
import pickle
import random
from typing import Dict, Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "starter"))
sys.path.insert(0, ROOT_DIR)

from game import Action, Observation, Street
from training.abstraction import get_preflop_bucket, get_postflop_bucket, make_infoset_key
from training.mccfr import ACTION_TO_CHAR
from runtime.policy import HeuristicPolicy


class CFRPolicy:
    """CFR-based policy querying pre-computed strategy tables."""

    def __init__(self, checkpoint_path: Optional[str] = None, seed: int = 42):
        self.rng = random.Random(seed)
        self.fallback = HeuristicPolicy(aggression=1.0, seed=seed)
        self.strategy_table: Dict[str, Dict[Action, float]] = {}

        if checkpoint_path and os.path.exists(checkpoint_path):
            self.load(checkpoint_path)

    def load(self, path: str):
        with open(path, "rb") as f:
            data = pickle.load(f)
        raw_sums = data.get("strategy_sum", {})
        # Normalize strategy sums into action probability distributions
        self.strategy_table = {}
        for info_set, action_counts in raw_sums.items():
            total = sum(action_counts.values())
            if total > 0:
                self.strategy_table[info_set] = {
                    a: count / total for a, count in action_counts.items()
                }

    def _history_str(self, obs: Observation) -> str:
        return "".join(ACTION_TO_CHAR[a.action] for a in obs.action_history)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        """Choose action using CFR mixed strategy, or fallback if unvisited."""
        # Always check when free and no raises legal
        if obs.to_call == 0 and Action.RAISE_HALF not in obs.legal_actions:
            return Action.CHECK_CALL

        # Compute information set key
        if obs.street == Street.PREFLOP:
            bucket = get_preflop_bucket(obs.hole_cards)
        else:
            bucket = get_postflop_bucket(obs.hole_cards, obs.board)

        hist = self._history_str(obs)
        info_set = make_infoset_key(obs.street, bucket, hist)

        strategy = self.strategy_table.get(info_set)
        if strategy:
            # Filter to legal actions and re-normalize
            legal_probs = {a: strategy.get(a, 0.0) for a in obs.legal_actions}
            total = sum(legal_probs.values())
            if total > 0:
                actions = list(legal_probs.keys())
                weights = [legal_probs[a] / total for a in actions]
                return self.rng.choices(actions, weights=weights, k=1)[0]

        # Unvisited infoset: use heuristic fallback
        return self.fallback.choose_action(obs, memory)

