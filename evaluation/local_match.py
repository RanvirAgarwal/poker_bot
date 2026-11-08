"""
evaluation/local_match.py - Run matches locally without HTTP overhead.

Directly calls bot functions to evaluate strategy quality quickly.
Avoids the HTTP server overhead for fast iteration.
"""

from __future__ import annotations

import sys
import os
import time
import math
import statistics
from dataclasses import dataclass
from typing import Callable, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "starter"))

from game import (
    Game, Deal, Action, Observation, HandResult, AgentConfig,
    make_deal, button_for_deal, default_action,
    BIG_BLIND, STARTING_STACK, NUM_DEALS, CHOP_Z,
)
from evaluator import warmup, card_to_str


@dataclass
class LocalMatchResult:
    """Result of a local match (both halves combined)."""
    num_deals: int
    paired_bb: list[float]
    mean_bb: float
    std_bb: float
    stderr_bb: float
    ci: tuple[float, float]
    verdict: str
    half1_chips: int
    half2_chips: int
    elapsed_seconds: float
    agent1_errors: int
    agent2_errors: int
    logs: Optional[dict[str, list]] = None


def play_local_half(
    agent1_fn: Callable[[Observation, dict], Action],
    agent2_fn: Callable[[Observation, dict], Action],
    agent1_end_fn: Callable[[HandResult, dict], None] | None,
    agent2_end_fn: Callable[[HandResult, dict], None] | None,
    agent1_new_half_fn: Callable[[AgentConfig, dict], None] | None,
    agent2_new_half_fn: Callable[[AgentConfig, dict], None] | None,
    seed: str,
    half: int,
    num_deals: int = NUM_DEALS,
    keep_logs: bool = False,
) -> tuple[list[int], list[int], int, int, Optional[list]]:
    """Play one half locally. Returns (nets_a1, nets_a2, a1_errors, a2_errors, logs)."""
    a1_seat = 0 if half == 1 else 1
    a2_seat = 1 - a1_seat
    fns = [None, None]
    end_fns = [None, None]
    new_half_fns = [None, None]
    memories = [{}, {}]
    fns[a1_seat] = agent1_fn
    fns[a2_seat] = agent2_fn
    end_fns[a1_seat] = agent1_end_fn
    end_fns[a2_seat] = agent2_end_fn
    new_half_fns[a1_seat] = agent1_new_half_fn
    new_half_fns[a2_seat] = agent2_new_half_fn

    config = AgentConfig(num_hands=num_deals)
    for seat in (0, 1):
        if new_half_fns[seat] is not None:
            try:
                new_half_fns[seat](config, memories[seat])
            except Exception as e:
                print(f"[ERROR] seat {seat} new_half raised: {e}")

    nets_a1 = []
    nets_a2 = []
    errors = [0, 0]
    logs = [] if keep_logs else None

    for d in range(num_deals):
        button = button_for_deal(d)
        game = Game(make_deal(seed, d), button, hand_index=d)

        while not game.is_terminal:
            seat = game.to_act
            obs = game.observation(seat)
            try:
                action = fns[seat](obs, memories[seat])
                if action not in obs.legal_actions:
                    errors[seat] += 1
                    action = default_action(obs.to_call)
            except Exception as e:
                errors[seat] += 1
                if errors[seat] <= 3:
                    print(f"[ERROR] seat {seat} choose_action raised: {e}")
                action = default_action(obs.to_call)
            game.apply(action)

        res = game.result()
        nets_a1.append(res.nets[a1_seat])
        nets_a2.append(res.nets[a2_seat])

        if logs is not None:
            logs.append({
                "half": half,
                "deal_index": d,
                "button_seat": button,
                "hole_cards": [[card_to_str(c) for c in hole] for hole in game.deal.hole_cards],
                "board": [card_to_str(c) for c in game.deal.board],
                "actions": [r.to_dict() for r in res.history],
                "pot": res.pot,
                "went_to_showdown": res.went_to_showdown,
                "nets": list(res.nets),
            })

        # Deliver hand results
        for seat in (0, 1):
            hr = game.hand_result(seat)
            if end_fns[seat] is not None:
                try:
                    end_fns[seat](hr, memories[seat])
                except Exception as e:
                    errors[seat] += 1
                    if errors[seat] <= 3:
                        print(f"[ERROR] seat {seat} on_hand_end raised: {e}")

    return nets_a1, nets_a2, errors[a1_seat], errors[a2_seat], logs


def play_local_match(
    agent1_fn: Callable[[Observation, dict], Action],
    agent2_fn: Callable[[Observation, dict], Action],
    agent1_end_fn: Callable[[HandResult, dict], None] | None = None,
    agent2_end_fn: Callable[[HandResult, dict], None] | None = None,
    agent1_new_half_fn: Callable[[AgentConfig, dict], None] | None = None,
    agent2_new_half_fn: Callable[[AgentConfig, dict], None] | None = None,
    seed: str = "eval_1",
    num_deals: int = 200,
    keep_logs: bool = False,
) -> LocalMatchResult:
    """Play a complete duplicate match (both halves) locally."""
    warmup()
    start = time.perf_counter()

    # Half 1: agent1 = seat 0
    h1_a1, h1_a2, h1_e1, h1_e2, logs_h1 = play_local_half(
        agent1_fn, agent2_fn, agent1_end_fn, agent2_end_fn,
        agent1_new_half_fn, agent2_new_half_fn,
        seed, 1, num_deals, keep_logs=keep_logs,
    )

    # Half 2: agent1 = seat 1
    h2_a1, h2_a2, h2_e1, h2_e2, logs_h2 = play_local_half(
        agent1_fn, agent2_fn, agent1_end_fn, agent2_end_fn,
        agent1_new_half_fn, agent2_new_half_fn,
        seed, 2, num_deals, keep_logs=keep_logs,
    )

    elapsed = time.perf_counter() - start

    # Pair results
    paired_chips = [h1_a1[d] + h2_a1[d] for d in range(num_deals)]
    paired_bb = [c / BIG_BLIND for c in paired_chips]

    mean = sum(paired_chips) / BIG_BLIND / num_deals if num_deals else 0.0
    std = statistics.stdev(paired_bb) if num_deals > 1 else 0.0
    stderr = std / math.sqrt(num_deals) if num_deals else 0.0
    ci = (mean - CHOP_Z * stderr, mean + CHOP_Z * stderr)

    if ci[0] > 0:
        verdict = "AGENT1_WIN"
    elif ci[1] < 0:
        verdict = "AGENT2_WIN"
    else:
        verdict = "CHOP"

    combined_logs = {"half1": logs_h1, "half2": logs_h2} if keep_logs else None

    return LocalMatchResult(
        num_deals=num_deals,
        paired_bb=paired_bb,
        mean_bb=mean,
        std_bb=std,
        stderr_bb=stderr,
        ci=ci,
        verdict=verdict,
        half1_chips=sum(h1_a1),
        half2_chips=sum(h2_a1),
        elapsed_seconds=elapsed,
        agent1_errors=h1_e1 + h2_e1,
        agent2_errors=h1_e2 + h2_e2,
        logs=combined_logs,
    )


def format_local_result(result: LocalMatchResult, name1: str = "agent1", name2: str = "agent2") -> str:
    """Format a local match result for display."""
    lines = [
        f"Local Match: {result.num_deals} deals (duplicate)",
        f"{name1}: {result.mean_bb:+.3f} bb/deal  (std {result.std_bb:.2f}, stderr {result.stderr_bb:.3f})",
        f"95% CI: [{result.ci[0]:+.3f}, {result.ci[1]:+.3f}] bb/deal",
        f"Verdict: {result.verdict}",
        f"Half 1: {name1} {result.half1_chips:+d} chips",
        f"Half 2: {name1} {result.half2_chips:+d} chips",
        f"Errors: {name1}={result.agent1_errors}, {name2}={result.agent2_errors}",
        f"Time: {result.elapsed_seconds:.2f}s ({result.num_deals * 2 / max(0.001, result.elapsed_seconds):,.0f} hands/s)",
    ]
    return "\n".join(lines)

