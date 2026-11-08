"""
training/run_kuhn_benchmark.py - Benchmark GenericMCCFRTrainer on Kuhn Poker with exact NashConv.
"""

from __future__ import annotations

import sys
import os
import random

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from training.generic_mccfr import GenericMCCFRTrainer
from training.kuhn_exact import KuhnGame, compute_nash_conv, evaluate_game_value, KUHN_DEALS


def run_kuhn_convergence_study(budgets: list[int] = None, seeds: list[int] = None):
    if budgets is None:
        budgets = [1000, 5000, 25000, 100000]
    if seeds is None:
        seeds = [42, 1337, 2026]

    print("=" * 85)
    print("EXACT KUHN POKER CFR CONVERGENCE STUDY")
    print("Analytical Game Value (P0): -1/18 = -0.05556 | Analytical NashConv: 0.00000")
    print("=" * 85)
    print(f"{'Budget':<10} | {'Seed':<6} | {'Game Value':<12} | {'BR_0 Val':<12} | {'BR_1 Val':<12} | {'NashConv':<12} | {'Exploitability':<14}")
    print("-" * 85)

    all_results = []
    for b in budgets:
        b_nashconvs = []
        b_vals = []
        for s in seeds:
            trainer = GenericMCCFRTrainer(seed=s)
            deck = [1, 2, 3]

            for _ in range(b):
                trainer.rng.shuffle(deck)
                deal = (deck[0], deck[1])

                g0 = KuhnGame(deal)
                trainer.traverse(g0, traversing_seat=0)

                g1 = KuhnGame(deal)
                trainer.traverse(g1, traversing_seat=1)

            strat_fn = trainer.get_average_strategy
            game_val = evaluate_game_value(strat_fn)
            nash_conv, exploitability, br0, br1 = compute_nash_conv(strat_fn)

            b_nashconvs.append(nash_conv)
            b_vals.append(game_val)

            print(f"{b:<10d} | {s:<6d} | {game_val:+10.5f}   | {br0:+10.5f}   | {br1:+10.5f}   | {nash_conv:10.5f}   | {exploitability:12.5f}")

        avg_nc = sum(b_nashconvs) / len(b_nashconvs)
        avg_val = sum(b_vals) / len(b_vals)
        print(f"--> Budget {b:6d} Mean: Game Value = {avg_val:+.5f} | NashConv = {avg_nc:.5f} | Exploitability = {avg_nc/2:.5f}\n")


if __name__ == "__main__":
    run_kuhn_convergence_study()

