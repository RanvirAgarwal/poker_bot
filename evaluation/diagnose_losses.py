"""
evaluation/diagnose_losses.py - Diagnose decision contexts where EquityBot_v1 loses against range-aware play.
"""

from __future__ import annotations

import sys
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from game import Game, Street, Action, make_deal, button_for_deal
from runtime.policy import HeuristicPolicy
from opponents.baselines import ActionConditionedRangeBot
from runtime.features import preflop_hand_quality, omaha_best_score


def diagnose_losses(num_deals: int = 50, seed: str = "diag_seed"):
    print("=" * 80)
    print("DIAGNOSTIC TRACE: EquityBot_v1 vs ActionConditionedRangeBot")
    print("=" * 80)

    p1 = HeuristicPolicy(seed=42)
    p2 = ActionConditionedRangeBot(seed=777)

    losses = []
    loss_by_street = {Street.PREFLOP: 0, Street.FLOP: 0, Street.TURN: 0, Street.RIVER: 0}
    loss_chip_sum_by_street = {Street.PREFLOP: 0, Street.FLOP: 0, Street.TURN: 0, Street.RIVER: 0}

    for d in range(num_deals):
        for half, a1_seat in ((1, 0), (2, 1)):
            btn = button_for_deal(d)
            deal = make_deal(f"{seed}_diag", d)
            game = Game(deal, button_seat=btn, hand_index=d)
            mem1 = {}
            mem2 = {}

            history_actions = []

            while not game.is_terminal:
                seat = game.to_act
                obs = game.observation(seat)
                if seat == a1_seat:
                    act = p1.choose_action(obs, mem1)
                    history_actions.append((seat, obs.street, act, obs.pot, obs.to_call, obs.my_bet, obs.opp_bet))
                else:
                    act = p2.choose_action(obs, mem2)
                    history_actions.append((seat, obs.street, act, obs.pot, obs.to_call, obs.my_bet, obs.opp_bet))
                game.apply(act)

            res = game.result()
            net1 = res.nets[a1_seat]
            if net1 < -5:  # meaningful loss
                # Identify last non-fold action taken by agent1
                last_street = res.history[-1].street if res.history else Street.PREFLOP
                loss_by_street[last_street] += 1
                loss_chip_sum_by_street[last_street] += abs(net1)
                losses.append({
                    "deal": d,
                    "half": half,
                    "net": net1,
                    "street": last_street,
                    "went_to_showdown": res.went_to_showdown,
                    "p1_hole": deal.hole_cards[a1_seat],
                    "p2_hole": deal.hole_cards[1 - a1_seat],
                    "board": res.board_revealed,
                    "actions": [(r.seat == a1_seat, r.street.name, r.action.name, r.amount) for r in res.history],
                })

    print(f"\nTotal Hands Analyzed: {num_deals * 2} | Hands with Loss > 5 chips: {len(losses)}")
    print("\nLoss Distribution by Final Street:")
    for st in (Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER):
        cnt = loss_by_street[st]
        chips = loss_chip_sum_by_street[st]
        print(f"  {st.name:<10}: {cnt:3d} losses ({chips:4d} chips lost)")

    print("\nRepresentative Losing Hands Analysis (Top 5 Biggest Losses):")
    losses.sort(key=lambda x: x["net"])
    for idx, l in enumerate(losses[:5], 1):
        print(f"\n[{idx}] Deal {l['deal']}, Half {l['half']}, Net: {l['net']} chips | Street: {l['street'].name} | Showdown: {l['went_to_showdown']}")
        print(f"    Actions: {l['actions']}")
        p1_score = omaha_best_score(l['p1_hole'], l['board']) if len(l['board']) >= 3 else 0
        p2_score = omaha_best_score(l['p2_hole'], l['board']) if len(l['board']) >= 3 else 0
        print(f"    Scores: P1={p1_score} (Cat {p1_score>>20}), P2={p2_score} (Cat {p2_score>>20})")


if __name__ == "__main__":
    diagnose_losses()

