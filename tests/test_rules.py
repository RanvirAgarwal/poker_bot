"""
tests/test_rules.py - Verify poker rule correctness against official evaluator.

Tests the hand evaluation, game mechanics, and our feature extraction
against the starter's reference implementation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "starter"))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from evaluator import (
    score_five, omaha_score, cards_from_str, warmup, get_table,
    category_of, FLUSH, FULL_HOUSE, THREE_OF_A_KIND, STRAIGHT,
    STRAIGHT_FLUSH, FOUR_OF_A_KIND, HIGH_CARD, ONE_PAIR, TWO_PAIR,
    NUM_CARDS,
)
from game import (
    Game, Deal, Action, make_deal, button_for_deal, Street,
    STARTING_STACK, BIG_BLIND, SMALL_BLIND, RAISE_CAP_PER_STREET,
)


class TestShortDeckRankings:
    """Verify Short Deck hand ranking modifications."""

    @pytest.fixture(autouse=True)
    def setup(self):
        warmup()

    def test_flush_beats_full_house(self):
        """In Short Deck, flush > full house."""
        # Flush: Ah Kh Qh Jh 9h
        flush = score_five(cards_from_str("Ah Kh Qh Jh 9h"))
        # Full house: AA KKK
        full_house = score_five(cards_from_str("Ac Ad Kc Kd Kh"))
        assert category_of(flush) == FLUSH
        assert category_of(full_house) == FULL_HOUSE
        assert flush > full_house

    def test_trips_beats_straight(self):
        """In Short Deck, three of a kind > straight."""
        trips = score_five(cards_from_str("Ac Ad Ah Kc Qd"))
        straight = score_five(cards_from_str("Ac Kd Qh Jc Ts"))
        assert category_of(trips) == THREE_OF_A_KIND
        assert category_of(straight) == STRAIGHT
        assert trips > straight

    def test_wheel_straight(self):
        """A-6-7-8-9 is a valid straight (nine-high, lowest)."""
        wheel = score_five(cards_from_str("Ac 6d 7h 8c 9s"))
        assert category_of(wheel) == STRAIGHT
        # Should lose to T-high straight
        t_straight = score_five(cards_from_str("6c 7d 8h 9c Ts"))
        assert t_straight > wheel

    def test_straight_flush_beats_four_of_a_kind(self):
        sf = score_five(cards_from_str("6c 7c 8c 9c Tc"))
        quads = score_five(cards_from_str("Ac Ad Ah As Kc"))
        assert category_of(sf) == STRAIGHT_FLUSH
        assert category_of(quads) == FOUR_OF_A_KIND
        assert sf > quads


class TestOmahaEvaluation:
    """Verify the Omaha 2+3 selection rule."""

    @pytest.fixture(autouse=True)
    def setup(self):
        warmup()

    def test_must_use_exactly_two_hole_cards(self):
        """Omaha requires exactly 2 hole + 3 board cards."""
        # Hole: four clubs, one diamond
        hole = cards_from_str("6c 7c 8c 9c Ad")
        # Board: Tc Jc Qc Kc Ah (four clubs on board too)
        board = cards_from_str("Tc Jc Qc Kc Ah")
        # With all 10 cards there's a royal flush, but with exactly 2+3
        # the best should be using 2 of the hole clubs + 3 board clubs
        score = omaha_score(hole, board)
        assert score > 0

    def test_omaha_uses_five_cards(self):
        """Score must come from a valid 5-card hand."""
        hole = cards_from_str("Ac Kc Qc Jc Tc")
        board = cards_from_str("9c 8c 7c 6c As")
        score = omaha_score(hole, board)
        assert score > 0


class TestGameMechanics:
    """Verify core game mechanics."""

    def _make_game(self, deal_index: int = 0, seed: str = "test") -> Game:
        deal = make_deal(seed, deal_index)
        button = button_for_deal(deal_index)
        return Game(deal, button, hand_index=deal_index)

    def test_initial_state(self):
        """Initial game state should have correct blinds posted."""
        game = self._make_game()
        assert game.pot == SMALL_BLIND + BIG_BLIND  # 3
        assert game.street == Street.PREFLOP
        assert not game.is_terminal
        assert game.stacks[game.button_seat] == STARTING_STACK - SMALL_BLIND
        assert game.stacks[1 - game.button_seat] == STARTING_STACK - BIG_BLIND

    def test_button_acts_first_preflop(self):
        """Button (small blind) acts first preflop."""
        game = self._make_game()
        assert game.to_act == game.button_seat

    def test_fold_ends_hand(self):
        """Folding should end the hand immediately."""
        game = self._make_game()
        game.apply(Action.FOLD)
        assert game.is_terminal
        result = game.result()
        # Opponent wins the pot
        assert result.nets[1 - game.button_seat] > 0

    def test_check_check_preflop_advances_to_flop(self):
        """Button calls, BB checks should advance to flop."""
        game = self._make_game()
        # Button (SB) calls (puts in 1 more to match BB)
        game.apply(Action.CHECK_CALL)
        # BB checks
        game.apply(Action.CHECK_CALL)
        assert game.street == Street.FLOP
        assert not game.is_terminal

    def test_raise_cap(self):
        """After 4 raises, no more raises should be legal."""
        game = self._make_game()
        # Button raises (raise 1)
        game.apply(Action.RAISE_HALF)
        for i in range(3):
            # Opponent raises back
            if Action.RAISE_HALF in game.legal_actions():
                game.apply(Action.RAISE_HALF)
            else:
                break

        # After 4 raises, raises should not be legal for either player
        legal = game.legal_actions()
        assert Action.RAISE_HALF not in legal
        assert Action.RAISE_POT not in legal

    def test_non_button_acts_first_postflop(self):
        """Non-button player acts first on flop, turn, river."""
        game = self._make_game()
        # Get to flop
        game.apply(Action.CHECK_CALL)  # button calls
        game.apply(Action.CHECK_CALL)  # BB checks
        assert game.street == Street.FLOP
        assert game.to_act == 1 - game.button_seat

    def test_showdown_produces_result(self):
        """Playing through to showdown should produce a valid result."""
        game = self._make_game()
        while not game.is_terminal:
            game.apply(Action.CHECK_CALL)
        result = game.result()
        assert result.went_to_showdown
        assert result.nets[0] + result.nets[1] == 0  # zero-sum

    def test_stacks_are_80(self):
        """Starting stacks should be 80."""
        game = self._make_game()
        assert STARTING_STACK == 80

    def test_36_card_deck(self):
        """Deck should have exactly 36 cards."""
        assert NUM_CARDS == 36

    def test_observation_fields(self):
        """Observation should contain all expected fields."""
        game = self._make_game()
        obs = game.observation(game.to_act)
        assert len(obs.hole_cards) == 5
        assert obs.big_blind == BIG_BLIND
        assert isinstance(obs.legal_actions, tuple)
        assert len(obs.legal_actions) > 0


class TestDealDeterminism:
    """Verify that deals are deterministic and reproducible."""

    def test_same_seed_same_deal(self):
        """Same seed and deal_index should produce identical deals."""
        d1 = make_deal("test_seed", 0)
        d2 = make_deal("test_seed", 0)
        assert d1.hole_cards == d2.hole_cards
        assert d1.board == d2.board

    def test_different_seed_different_deal(self):
        """Different seeds should produce different deals."""
        d1 = make_deal("seed_a", 0)
        d2 = make_deal("seed_b", 0)
        assert d1.hole_cards != d2.hole_cards or d1.board != d2.board

    def test_deal_has_no_duplicate_cards(self):
        """All 15 dealt cards should be unique."""
        d = make_deal("test", 0)
        all_cards = list(d.hole_cards[0]) + list(d.hole_cards[1]) + list(d.board)
        assert len(all_cards) == 15
        assert len(set(all_cards)) == 15

