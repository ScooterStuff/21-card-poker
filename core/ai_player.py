"""
21 Card Poker — AI opponent with strategic decision-making.
"""

import random
from .game_logic import Card, Player, GameState, Action, Phase, RANK_VALUES
from .hand_eval import evaluate_player_hand, ROYAL_FLUSH, FIVE_OF_A_KIND, FOUR_OF_A_KIND, FULL_HOUSE, STRAIGHT, THREE_OF_A_KIND, TWO_PAIR, PAIR


def hand_strength(hand: list[Card]) -> int:
    """Return a simple hand strength score (higher = better)."""
    score, name, joker = evaluate_player_hand(hand)
    # Invert rank so higher is better
    base = (9 - score[0]) * 1000
    for i, v in enumerate(score[1:], 1):
        base += v * (10 ** (5 - i))
    return base


class AIPlayer:
    """AI opponent for 21-card poker."""

    def __init__(self, difficulty: str = "medium"):
        self.difficulty = difficulty

    def choose_action(self, state: GameState, available: list[Action]) -> tuple[Action, int]:
        """Choose a betting action and raise amount. Returns (action, raise_amount)."""
        ai = state.player2
        opponent = state.player1
        score, name, joker = evaluate_player_hand(ai.hand)
        hand_rank = score[0]

        # Calculate max raise from engine perspective
        diff = max(state.bet_to_match - ai.current_bet, 0)
        actor_can_add = ai.chips - diff
        max_raise = min(actor_can_add, opponent.chips)
        max_raise = max(max_raise, 1)

        def pick_raise(fraction_low: float, fraction_high: float) -> int:
            """Pick a raise amount as a fraction of max raise."""
            lo = max(1, int(max_raise * fraction_low))
            hi = max(lo, int(max_raise * fraction_high))
            return random.randint(lo, hi)

        # Aggressiveness based on hand strength
        if hand_rank <= FOUR_OF_A_KIND:  # Royal flush, five/four of a kind
            # Very strong hand — raise big
            if Action.RAISE in available:
                return Action.RAISE, pick_raise(0.5, 1.0)
            if Action.CALL in available:
                return Action.CALL, 0
            if Action.CHECK in available:
                return Action.CHECK, 0

        elif hand_rank <= STRAIGHT:  # Full house, straight
            # Strong hand — usually raise medium, sometimes call
            if Action.RAISE in available and random.random() < 0.65:
                return Action.RAISE, pick_raise(0.25, 0.6)
            if Action.CALL in available:
                return Action.CALL, 0
            if Action.CHECK in available:
                return Action.CHECK, 0

        elif hand_rank == THREE_OF_A_KIND:
            # Decent hand
            if Action.RAISE in available and random.random() < 0.3:
                return Action.RAISE, pick_raise(0.1, 0.35)
            if Action.CALL in available:
                return Action.CALL, 0
            if Action.CHECK in available:
                return Action.CHECK, 0

        elif hand_rank == TWO_PAIR:
            # Moderate hand
            if Action.CALL in available:
                return Action.CALL, 0
            if Action.CHECK in available:
                return Action.CHECK, 0
            # Sometimes bluff-raise small
            if Action.RAISE in available and random.random() < 0.15:
                return Action.RAISE, pick_raise(0.05, 0.15)

        else:  # Pair
            # Weak hand
            if Action.CHECK in available:
                return Action.CHECK, 0
            if Action.CALL in available:
                diff_cost = state.bet_to_match - ai.current_bet
                if diff_cost <= 1 or random.random() < 0.5:
                    return Action.CALL, 0
                return Action.FOLD, 0
            # Bluff occasionally
            if Action.RAISE in available and random.random() < 0.1:
                return Action.RAISE, pick_raise(0.05, 0.15)

        # Fallback: check > call > fold
        if Action.CHECK in available:
            return Action.CHECK, 0
        if Action.CALL in available:
            return Action.CALL, 0
        return Action.FOLD, 0

    def choose_discards(self, state: GameState) -> list[int]:
        """Choose which card indices to discard during draw phase."""
        ai = state.player2
        hand = ai.hand
        score, name, joker = evaluate_player_hand(hand)
        hand_rank = score[0]

        # If we have a really strong hand, keep everything
        if hand_rank <= STRAIGHT:
            return []

        ranks = [c.rank for c in hand]
        rank_counts = {}
        for i, c in enumerate(hand):
            r = c.rank if not c.is_joker else "Joker"
            if r not in rank_counts:
                rank_counts[r] = []
            rank_counts[r].append(i)

        # Always keep the Joker
        keep_indices = set()
        if "Joker" in rank_counts:
            keep_indices.update(rank_counts["Joker"])

        # Keep cards that are part of pairs/trips
        for r, indices in rank_counts.items():
            if r == "Joker":
                continue
            if len(indices) >= 2:
                keep_indices.update(indices)

        # If three of a kind, keep the trips and discard the other two
        if hand_rank == THREE_OF_A_KIND:
            discard = [i for i in range(5) if i not in keep_indices]
            return discard

        # Two pair: keep both pairs, discard kicker
        if hand_rank == TWO_PAIR:
            discard = [i for i in range(5) if i not in keep_indices]
            return discard

        # One pair: keep pair (and joker if any), discard rest
        if hand_rank == PAIR:
            discard = [i for i in range(5) if i not in keep_indices]
            # Don't discard more than 3 cards strategically
            if len(discard) > 3:
                # Keep the highest kicker
                kicker_indices = [(i, hand[i].value) for i in discard]
                kicker_indices.sort(key=lambda x: x[1], reverse=True)
                keep_extra = kicker_indices[0][0]
                discard.remove(keep_extra)
            return discard

        # Fallback: discard lowest-value cards
        indexed = [(i, hand[i].value) for i in range(5) if not hand[i].is_joker]
        indexed.sort(key=lambda x: x[1])
        return [idx for idx, val in indexed[:2]]

