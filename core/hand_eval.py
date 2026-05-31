"""
21 Card Poker — Hand evaluation and comparison.
Handles Joker resolution, hand ranking, and tiebreaking.
"""

from itertools import product
from .game_logic import Card, JOKER, RANKS, SUITS, RANK_VALUES

# Hand rank constants (lower number = better hand)
FIVE_OF_A_KIND = 1
ROYAL_FLUSH = 2
FOUR_OF_A_KIND = 3
FULL_HOUSE = 4
STRAIGHT = 5
THREE_OF_A_KIND = 6
TWO_PAIR = 7
PAIR = 8

HAND_NAMES = {
    FIVE_OF_A_KIND: "Five of a Kind",
    ROYAL_FLUSH: "Royal Flush",
    FOUR_OF_A_KIND: "Four of a Kind",
    FULL_HOUSE: "Full House",
    STRAIGHT: "Straight",
    THREE_OF_A_KIND: "Three of a Kind",
    TWO_PAIR: "Two Pair",
    PAIR: "Pair",
}


def rank_val(rank: str) -> int:
    """Return numeric value of rank for comparison (higher is better)."""
    return RANK_VALUES.get(rank, 0)


def evaluate_hand_no_joker(cards: list[Card]) -> tuple:
    """
    Evaluate a 5-card hand with no joker.
    Returns (hand_rank, *tiebreakers) where lower hand_rank = better.
    Tiebreakers are tuples of rank values, highest first.
    """
    ranks = [c.rank for c in cards]
    suits = [c.suit for c in cards]

    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1

    sorted_counts = sorted(rank_counts.items(), key=lambda x: (x[1], rank_val(x[0])), reverse=True)

    # Check Five of a Kind (only possible via Joker substitution)
    if sorted_counts[0][1] == 5:
        return (FIVE_OF_A_KIND, rank_val(sorted_counts[0][0]))

    # Check Royal Flush: A-K-Q-J-10 all same suit
    if len(set(suits)) == 1 and set(ranks) == {"A", "K", "Q", "J", "10"}:
        return (ROYAL_FLUSH,)

    # Check Four of a Kind
    if sorted_counts[0][1] == 4:
        quad_rank = sorted_counts[0][0]
        kicker_rank = sorted_counts[1][0]
        return (FOUR_OF_A_KIND, rank_val(quad_rank), rank_val(kicker_rank))

    # Check Full House
    if sorted_counts[0][1] == 3 and sorted_counts[1][1] == 2:
        trips_rank = sorted_counts[0][0]
        pair_rank = sorted_counts[1][0]
        return (FULL_HOUSE, rank_val(trips_rank), rank_val(pair_rank))

    # Check Straight: only A-K-Q-J-10 is possible
    if set(ranks) == {"A", "K", "Q", "J", "10"}:
        return (STRAIGHT,)

    # Check Three of a Kind
    if sorted_counts[0][1] == 3:
        trips_rank = sorted_counts[0][0]
        kickers = sorted([rank_val(r) for r, c in sorted_counts if c != 3], reverse=True)
        return (THREE_OF_A_KIND, rank_val(trips_rank), *kickers)

    # Check Two Pair
    pairs = [(r, c) for r, c in sorted_counts if c == 2]
    if len(pairs) == 2:
        pair_vals = sorted([rank_val(p[0]) for p in pairs], reverse=True)
        kicker = [rank_val(r) for r, c in sorted_counts if c == 1]
        return (TWO_PAIR, pair_vals[0], pair_vals[1], *kicker)

    # Pair (must have at least a pair due to pigeonhole)
    if sorted_counts[0][1] == 2:
        pair_rank = sorted_counts[0][0]
        kickers = sorted([rank_val(r) for r, c in sorted_counts if c == 1], reverse=True)
        return (PAIR, rank_val(pair_rank), *kickers)

    # Should not reach here with 5 cards from 5 ranks, but just in case
    vals = sorted([rank_val(r) for r in ranks], reverse=True)
    return (9, *vals)


def evaluate_hand_with_joker(cards: list[Card]) -> tuple[tuple, Card]:
    """
    Evaluate a hand that contains the Joker.
    Try every possible card the Joker could become and pick the best.
    Returns (best_score, resolved_card).
    """
    non_joker = [c for c in cards if not c.is_joker]
    best_score = None
    best_card = None

    for r in RANKS:
        for s in SUITS:
            candidate = Card(rank=r, suit=s)
            test_hand = non_joker + [candidate]
            score = evaluate_hand_no_joker(test_hand)
            if best_score is None or compare_scores(score, best_score) > 0:
                best_score = score
                best_card = candidate

    return best_score, best_card


def compare_scores(a: tuple, b: tuple) -> int:
    """
    Compare two hand scores.
    Returns: positive if a wins, negative if b wins, 0 if tie.
    Lower hand_rank index = better hand, but within tiebreakers higher = better.
    """
    # Compare hand rank (lower = better)
    if a[0] != b[0]:
        return 1 if a[0] < b[0] else -1  # Lower rank number is better → positive means a wins

    # Same hand rank: compare tiebreakers (higher = better)
    max_len = max(len(a), len(b))
    for i in range(1, max_len):
        va = a[i] if i < len(a) else 0
        vb = b[i] if i < len(b) else 0
        if va != vb:
            return 1 if va > vb else -1

    return 0  # Exact tie


def evaluate_player_hand(cards: list[Card]) -> tuple[tuple, str, Card | None]:
    """
    Evaluate a player's hand.
    Returns (score_tuple, hand_name, joker_resolved_card_or_None).
    """
    has_joker = any(c.is_joker for c in cards)

    if has_joker:
        # Five of a Kind check: need 4 of same rank + joker
        score, resolved = evaluate_hand_with_joker(cards)
        hand_name = HAND_NAMES.get(score[0], "Unknown")
        return score, hand_name, resolved
    else:
        score = evaluate_hand_no_joker(cards)
        hand_name = HAND_NAMES.get(score[0], "Unknown")
        return score, hand_name, None


def determine_winner(hand1: list[Card], hand2: list[Card]) -> tuple[int, str, str, Card | None, Card | None]:
    """
    Compare two hands.
    Returns (result, hand1_name, hand2_name, joker1, joker2)
    result: 1 if hand1 wins, -1 if hand2 wins, 0 if tie.
    """
    score1, name1, joker1 = evaluate_player_hand(hand1)
    score2, name2, joker2 = evaluate_player_hand(hand2)

    result = compare_scores(score1, score2)

    return result, name1, name2, joker1, joker2
