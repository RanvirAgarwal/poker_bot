"""
training/audit_coverage.py - Audit CFR information-set coverage and fallback rates.

Evaluates an exported CFR model checkpoint on held-out deals to measure:
- Decision points per street
- Strategy table lookup hit rate vs unvisited fallback rate
- Action distribution (frequencies of Fold, Check/Call, Raise Half, Raise Pot)
- Most frequently visited information sets
"""

from __future__ import annotations

import sys
import os
import pickle
from collections import Counter, defaultdict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from game import Game, Street, Action, make_deal, button_for_deal
from runtime.cfr_policy import CFRPolicy
from training.abstraction import get_preflop_bucket, get_postflop_bucket, make_infoset_key
from training.mccfr import ACTION_TO_CHAR


def audit_cfr_coverage(checkpoint_path: str = "assets/cfr_blueprint_v1.pkl", num_deals: int = 500):
    print("=" * 70)
    print(f"CFR COVERAGE AUDIT: {checkpoint_path}")
    print(f"Testing on {num_deals} held-out deals (1,000 hands)")
    print("=" * 70)

    if not os.path.exists(checkpoint_path):
        print(f"Error: {checkpoint_path} not found.")
        return

    with open(checkpoint_path, "rb") as f:
        data = pickle.load(f)

    strategy_table = data.get("strategy_sum", {})
    total_stored_infosets = len(strategy_table)
    iterations = data.get("iterations", 0)
    print(f"Loaded checkpoint: {iterations} iterations, {total_stored_infosets:,} stored InfoSets\n")

    # Evaluation counters by street
    total_decisions_by_street = Counter()
    hits_by_street = Counter()
    misses_by_street = Counter()
    action_counts_by_street = defaultdict(Counter)
    infoset_hits_counter = Counter()

    # Simulate against a mixed opponent to generate realistic game trees
    import random
    eval_rng = random.Random(9999)

    for d in range(num_deals):
        for btn in (0, 1):
            deal = make_deal("held_out_audit", d)
            game = Game(deal, button_seat=btn, hand_index=d)

            while not game.is_terminal:
                seat = game.to_act
                street = game.street
                hole = game.deal.hole_cards[seat]

                if street == Street.PREFLOP:
                    bucket = get_preflop_bucket(hole)
                else:
                    visible = [3, 4, 5][street - 1]
                    board = game.deal.board[:visible]
                    bucket = get_postflop_bucket(hole, board)

                hist = "".join(ACTION_TO_CHAR[r.action] for r in game.history)
                info_key = make_infoset_key(street, bucket, hist)

                total_decisions_by_street[street] += 1

                if info_key in strategy_table:
                    hits_by_street[street] += 1
                    infoset_hits_counter[info_key] += 1
                else:
                    misses_by_street[street] += 1

                # Progress the game
                legal = game.legal_actions()
                if info_key in strategy_table:
                    sums = strategy_table[info_key]
                    probs = [sums.get(a, 0.0) for a in legal]
                    if sum(probs) > 0:
                        chosen = eval_rng.choices(legal, weights=probs, k=1)[0]
                    else:
                        chosen = eval_rng.choice(legal)
                else:
                    # Random/check fallback
                    chosen = Action.CHECK_CALL if Action.CHECK_CALL in legal else Action.FOLD

                action_counts_by_street[street][chosen] += 1
                game.apply(chosen)

    print(f"{'Street':<10} | {'Decisions':<10} | {'CFR Hits':<10} | {'Hit Rate':<10} | {'Fallback Rate':<14}")
    print("-" * 62)
    street_names = {Street.PREFLOP: "PREFLOP", Street.FLOP: "FLOP", Street.TURN: "TURN", Street.RIVER: "RIVER"}
    tot_dec = sum(total_decisions_by_street.values())
    tot_hits = sum(hits_by_street.values())

    for st in (Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER):
        dec = total_decisions_by_street[st]
        hits = hits_by_street[st]
        hit_pct = (hits / dec * 100) if dec else 0.0
        miss_pct = 100.0 - hit_pct
        print(f"{street_names[st]:<10} | {dec:<10d} | {hits:<10d} | {hit_pct:8.1f}% | {miss_pct:8.1f}%")

    print("-" * 62)
    overall_hit_pct = (tot_hits / tot_dec * 100) if tot_dec else 0.0
    print(f"{'OVERALL':<10} | {tot_dec:<10d} | {tot_hits:<10d} | {overall_hit_pct:8.1f}% | {100.0 - overall_hit_pct:8.1f}%\n")

    print("Top 10 Most Frequently Visited Information Sets:")
    for rank, (info_key, cnt) in enumerate(infoset_hits_counter.most_common(10), 1):
        action_dist = strategy_table.get(info_key, {})
        tot_wt = sum(action_dist.values())
        dist_str = ", ".join(f"{a.name}: {wt/tot_wt:.2f}" for a, wt in action_dist.items()) if tot_wt else "uniform"
        print(f"  {rank:2d}. {info_key:<20} (seen {cnt:4d}x) -> [{dist_str}]")


if __name__ == "__main__":
    ckpt = sys.argv[1] if len(sys.argv) > 1 else "assets/cfr_blueprint_v1.pkl"
    audit_cfr_coverage(ckpt)

