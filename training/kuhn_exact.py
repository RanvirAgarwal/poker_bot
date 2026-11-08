"""
training/kuhn_exact.py - Exact Best-Response and NashConv evaluation for Kuhn Poker.

Provides exact analytical ground truth for auditing the GenericMCCFRTrainer.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from training.generic_mccfr import ExtensiveGame


class KuhnGame(ExtensiveGame):
    """Kuhn Poker extensive-form game conforming to ExtensiveGame protocol."""

    def __init__(self, cards: Tuple[int, int]):
        self.cards = cards  # (p0_card, p1_card), 1=J, 2=Q, 3=K
        self.history: List[str] = []
        self._terminal = False
        self._to_act = 0
        self._payoffs = [0.0, 0.0]

    @property
    def is_terminal(self) -> bool:
        return self._terminal

    @property
    def to_act(self) -> int:
        return self._to_act

    def legal_actions(self) -> List[str]:
        if self._terminal:
            return []
        h = "".join(self.history)
        if h == "":
            return ["C", "B"]   # Check, Bet
        if h == "C":
            return ["C", "B"]   # Check, Bet
        if h == "B":
            return ["F", "C"]   # Fold, Call
        if h == "CB":
            return ["F", "C"]   # Fold, Call
        return []

    def clone(self) -> "KuhnGame":
        g = KuhnGame(self.cards)
        g.history = self.history[:]
        g._terminal = self._terminal
        g._to_act = self._to_act
        g._payoffs = self._payoffs[:]
        return g

    def apply(self, action: str) -> None:
        self.history.append(action)
        h = "".join(self.history)
        p0, p1 = self.cards

        if h == "CC":
            self._terminal = True
            win = 0 if p0 > p1 else 1
            self._payoffs = [1.0, -1.0] if win == 0 else [-1.0, 1.0]
        elif h == "CBF":
            self._terminal = True
            self._payoffs = [-1.0, 1.0]
        elif h == "CBC":
            self._terminal = True
            win = 0 if p0 > p1 else 1
            self._payoffs = [2.0, -2.0] if win == 0 else [-2.0, 2.0]
        elif h == "BF":
            self._terminal = True
            self._payoffs = [1.0, -1.0]
        elif h == "BC":
            self._terminal = True
            win = 0 if p0 > p1 else 1
            self._payoffs = [2.0, -2.0] if win == 0 else [-2.0, 2.0]
        else:
            self._to_act = 1 - self._to_act

    def payoffs(self, traversing_seat: int) -> float:
        return self._payoffs[traversing_seat]

    def info_set_key(self, seat: int) -> str:
        card = self.cards[seat]
        return f"{card}:{''.join(self.history)}"


# All 6 possible card deals in Kuhn poker
KUHN_DEALS = [
    (1, 2), (1, 3),
    (2, 1), (2, 3),
    (3, 1), (3, 2),
]


def evaluate_game_value(strategy_fn) -> float:
    """Compute expected game value for Player 0 under the given strategy."""
    total_val = 0.0

    def get_reach_payoff(g: KuhnGame, p0_prob: float, p1_prob: float) -> float:
        if g.is_terminal:
            return p0_prob * p1_prob * g.payoffs(0)
        seat = g.to_act
        info_set = g.info_set_key(seat)
        legal = g.legal_actions()
        strat = strategy_fn(info_set, legal)
        val = 0.0
        for a in legal:
            p = strat.get(a, 0.0)
            if p > 0:
                nxt = g.clone()
                nxt.apply(a)
                if seat == 0:
                    val += get_reach_payoff(nxt, p0_prob * p, p1_prob)
                else:
                    val += get_reach_payoff(nxt, p0_prob, p1_prob * p)
        return val

    for deal in KUHN_DEALS:
        g = KuhnGame(deal)
        total_val += get_reach_payoff(g, 1.0, 1.0)

    return total_val / len(KUHN_DEALS)


def compute_best_response_value(strategy_fn, target_player: int) -> float:
    """Compute maximum expected payoff target_player can achieve against opponent strategy_fn.

    Uses backward induction on the decision tree.
    """
    opponent = 1 - target_player

    def tree_val(g: KuhnGame) -> float:
        if g.is_terminal:
            return g.payoffs(target_player)
        seat = g.to_act
        info_set = g.info_set_key(seat)
        legal = g.legal_actions()

        if seat == target_player:
            # Best response maximizes expected payoff
            return max(tree_val(g_nxt) for g_nxt in [g.clone() for _ in legal])  # will set action below
        else:
            # Opponent plays fixed strategy
            strat = strategy_fn(info_set, legal)
            val = 0.0
            for a in legal:
                nxt = g.clone()
                nxt.apply(a)
                val += strat.get(a, 0.0) * tree_val(nxt)
            return val

    # Because target player can condition actions on their information set,
    # we solve for the optimal policy per information set across deals.
    # In Kuhn poker, each infoset of target_player is visited under known conditional deals.
    # Player 0 Infosets: 1:, 2:, 3:, 1:CB, 2:CB, 3:CB
    # Player 1 Infosets: 1:C, 2:C, 3:C, 1:B, 2:B, 3:B
    from itertools import product

    if target_player == 0:
        # Player 0 chooses actions for root and for after CB
        # There are 3 root infosets ("1:", "2:", "3:") and 3 CB infosets ("1:CB", "2:CB", "3:CB")
        # Each has 2 actions -> 2^6 = 64 pure strategies!
        best_val = -float("inf")
        p0_infos = ["1:", "2:", "3:", "1:CB", "2:CB", "3:CB"]
        action_choices = [["C", "B"], ["C", "B"], ["C", "B"], ["F", "C"], ["F", "C"], ["F", "C"]]

        for pure in product(*action_choices):
            pure_dict = dict(zip(p0_infos, pure))

            def p0_strat(info, legal):
                if info in pure_dict:
                    return {a: (1.0 if a == pure_dict[info] else 0.0) for a in legal}
                return {a: 1.0 / len(legal) for a in legal}

            # Evaluate this pure strategy against opponent's strategy
            total = 0.0
            for deal in KUHN_DEALS:
                g = KuhnGame(deal)
                # Roll out
                def sim(cur: KuhnGame, prob: float) -> float:
                    if cur.is_terminal:
                        return prob * cur.payoffs(0)
                    if cur.to_act == 0:
                        a = pure_dict[cur.info_set_key(0)]
                        nxt = cur.clone()
                        nxt.apply(a)
                        return sim(nxt, prob)
                    else:
                        opp_strat = strategy_fn(cur.info_set_key(1), cur.legal_actions())
                        v = 0.0
                        for a, p in opp_strat.items():
                            if p > 0:
                                nxt = cur.clone()
                                nxt.apply(a)
                                v += sim(nxt, prob * p)
                        return v
                total += sim(g, 1.0)
            avg = total / len(KUHN_DEALS)
            if avg > best_val:
                best_val = avg
        return best_val

    else:
        # Player 1 chooses actions for C and for B
        # 3 infosets for C ("1:C", "2:C", "3:C") with ["C", "B"]
        # 3 infosets for B ("1:B", "2:B", "3:B") with ["F", "C"]
        # 2^6 = 64 pure strategies!
        best_val = -float("inf")
        p1_infos = ["1:C", "2:C", "3:C", "1:B", "2:B", "3:B"]
        action_choices = [["C", "B"], ["C", "B"], ["C", "B"], ["F", "C"], ["F", "C"], ["F", "C"]]

        for pure in product(*action_choices):
            pure_dict = dict(zip(p1_infos, pure))

            total = 0.0
            for deal in KUHN_DEALS:
                g = KuhnGame(deal)
                def sim(cur: KuhnGame, prob: float) -> float:
                    if cur.is_terminal:
                        return prob * cur.payoffs(1)
                    if cur.to_act == 0:
                        p0_strat = strategy_fn(cur.info_set_key(0), cur.legal_actions())
                        v = 0.0
                        for a, p in p0_strat.items():
                            if p > 0:
                                nxt = cur.clone()
                                nxt.apply(a)
                                v += sim(nxt, prob * p)
                        return v
                    else:
                        a = pure_dict[cur.info_set_key(1)]
                        nxt = cur.clone()
                        nxt.apply(a)
                        return sim(nxt, prob)
                total += sim(g, 1.0)
            avg = total / len(KUHN_DEALS)
            if avg > best_val:
                best_val = avg
        return best_val


def compute_nash_conv(strategy_fn) -> Tuple[float, float, float, float]:
    """Compute NashConv = BR_0(strat) + BR_1(strat).

    Returns (nash_conv, exploitability, br0_val, br1_val).
    At Nash equilibrium:
      br0_val = -1/18 (-0.05556)
      br1_val = +1/18 (+0.05556)
      nash_conv = 0.0
      exploitability = 0.0
    """
    br0 = compute_best_response_value(strategy_fn, target_player=0)
    br1 = compute_best_response_value(strategy_fn, target_player=1)
    nash_conv = br0 + br1
    exploitability = nash_conv / 2.0
    return nash_conv, exploitability, br0, br1

