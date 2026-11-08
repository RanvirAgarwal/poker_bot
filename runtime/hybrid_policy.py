"""
runtime/hybrid_policy.py - Hybrid policy combining CFR equilibrium defense with adaptive exploitation.

Design:
- Uses CFR blueprint by default to prevent exploitation from strong/adaptive opponents.
- If within-half observations detect extreme passive/calling station leaks, adapts dynamically to value-extract.
"""

from __future__ import annotations

import sys
import os
import random
from typing import Optional

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from game import Action, Observation, Street
from runtime.policy import HeuristicPolicy
from runtime.cfr_policy import CFRPolicy
from runtime.opponent import OpponentModel


class HybridPolicy:
    """Combines CFR unexploitability with adaptive exploitation."""

    def __init__(self, cfr_checkpoint: str = "assets/cfr_blueprint_10k.pkl", seed: int = 42):
        self.rng = random.Random(seed)
        self.cfr = CFRPolicy(checkpoint_path=cfr_checkpoint, seed=seed)
        self.heuristic = HeuristicPolicy(aggression=1.0, seed=seed)

    def choose_action(self, obs: Observation, memory: dict) -> Action:
        # Check opponent tendencies from within-half memory
        stats = OpponentModel.get_stats(memory)
        hands_seen = stats.get("hands_seen", 0)

        # In the first 5 hands, play CFR to avoid leaking information
        if hands_seen < 5:
            return self.cfr.choose_action(obs, memory)

        # Detect Calling Station (never folds, high showdowns, low aggression)
        showdown_rate = stats.get("showdown_rate", 0.0)
        opp_net = stats.get("avg_net_per_hand", 0.0)

        # If opponent goes to showdown on > 45% of hands, use HeuristicPolicy to maximize value extraction
        if showdown_rate > 0.45:
            return self.heuristic.choose_action(obs, memory)

        # If facing multiple raises on a single street (hyper-aggressive), use Heuristic equity call
        if obs.raises_this_street >= 2:
            return self.heuristic.choose_action(obs, memory)

        # Default: play robust CFR equilibrium strategy
        return self.cfr.choose_action(obs, memory)
