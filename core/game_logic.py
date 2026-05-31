"""
21 Card Poker — Core game logic: deck, dealing, betting, round flow.
"""

import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# ── Card Definitions ──────────────────────────────────────────────

RANKS = ["A", "K", "Q", "J", "10"]
SUITS = ["♠", "♥", "♦", "♣"]
RANK_VALUES = {"A": 5, "K": 4, "Q": 3, "J": 2, "10": 1}

SUIT_COLORS = {"♠": "black", "♣": "black", "♥": "red", "♦": "red"}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str
    is_joker: bool = False

    def __str__(self):
        if self.is_joker:
            return "🃏"
        return f"{self.rank}{self.suit}"

    def __repr__(self):
        return self.__str__()

    @property
    def value(self):
        if self.is_joker:
            return 100  # Joker sorts high
        return RANK_VALUES.get(self.rank, 0)

    @property
    def color(self):
        if self.is_joker:
            return "purple"
        return SUIT_COLORS.get(self.suit, "black")


JOKER = Card(rank="Joker", suit="", is_joker=True)


def make_deck() -> list[Card]:
    """Create a shuffled 21-card deck."""
    cards = [Card(rank=r, suit=s) for r in RANKS for s in SUITS]
    cards.append(JOKER)
    random.shuffle(cards)
    return cards


# ── Game State ────────────────────────────────────────────────────

class Phase(Enum):
    FORCED_BETS = auto()
    PRE_DRAW_BET = auto()
    DRAW = auto()
    POST_DRAW_BET = auto()
    SHOWDOWN = auto()
    ROUND_OVER = auto()
    GAME_OVER = auto()


class Action(Enum):
    FOLD = "Fold"
    CHECK = "Check"
    CALL = "Call"
    RAISE = "Raise"


@dataclass
class Player:
    name: str
    chips: int
    hand: list = field(default_factory=list)
    is_human: bool = True
    current_bet: int = 0  # Amount bet THIS round

    def reset_hand(self):
        self.hand = []
        self.current_bet = 0


@dataclass
class GameState:
    player1: Player          # Human
    player2: Player          # AI
    starter: Player = None   # S role
    follower: Player = None  # F role
    pot: int = 0
    deck: list = field(default_factory=list)
    discard_pile: list = field(default_factory=list)
    phase: Phase = Phase.FORCED_BETS
    current_actor: Player = None
    bet_to_match: int = 0
    round_number: int = 0
    round_winner: Optional[Player] = None
    winner_reason: str = ""
    last_action_text: str = ""
    follower_discarded: int = -1
    starter_discarded: int = -1
    draw_sub_phase: str = ""  # "follower_draw" or "starter_draw"
    joker_resolved_as: Optional[Card] = None

    # For post-draw betting tracking
    first_actor_checked: bool = False


class GameEngine:
    """Manages the full game flow for 21-card poker."""

    def __init__(self, base_bet: int = 1, starting_chips: int = 50):
        self.base_bet = base_bet
        self.starting_chips = starting_chips
        self.state: Optional[GameState] = None

    def new_game(self) -> GameState:
        p1 = Player("You", self.starting_chips, is_human=True)
        p2 = Player("Opponent", self.starting_chips, is_human=False)
        self.state = GameState(player1=p1, player2=p2)
        self.state.starter = p1
        self.state.follower = p2
        self.state.round_number = 0
        return self.state

    def start_round(self):
        s = self.state
        s.round_number += 1
        s.pot = 0
        s.round_winner = None
        s.winner_reason = ""
        s.last_action_text = ""
        s.follower_discarded = -1
        s.starter_discarded = -1
        s.draw_sub_phase = ""
        s.first_actor_checked = False
        s.joker_resolved_as = None

        s.player1.reset_hand()
        s.player2.reset_hand()

        # Forced bets
        starter_bet = min(2 * self.base_bet, s.starter.chips)
        follower_bet = min(1 * self.base_bet, s.follower.chips)

        s.starter.chips -= starter_bet
        s.starter.current_bet = starter_bet
        s.follower.chips -= follower_bet
        s.follower.current_bet = follower_bet
        s.pot = starter_bet + follower_bet
        s.bet_to_match = starter_bet

        # Deal
        s.deck = make_deck()
        for _ in range(5):
            s.player1.hand.append(s.deck.pop())
            s.player2.hand.append(s.deck.pop())

        # Sort hands
        s.player1.hand.sort(key=lambda c: c.value, reverse=True)
        s.player2.hand.sort(key=lambda c: c.value, reverse=True)

        s.discard_pile = []

        # Pre-draw betting: follower acts first
        s.phase = Phase.PRE_DRAW_BET
        s.current_actor = s.follower

    def get_available_actions(self) -> list[Action]:
        s = self.state
        actions = []
        actor = s.current_actor
        opponent = s.player1 if actor == s.player2 else s.player2

        if s.phase == Phase.PRE_DRAW_BET:
            diff = s.bet_to_match - actor.current_bet
            if diff > 0:
                actions.append(Action.CALL)
            # Can raise if actor has chips beyond the call AND opponent has chips to cover
            if actor.chips > max(diff, 0) and opponent.chips > 0:
                actions.append(Action.RAISE)
            actions.append(Action.FOLD)

        elif s.phase == Phase.POST_DRAW_BET:
            diff = s.bet_to_match - actor.current_bet
            if diff == 0:
                actions.append(Action.CHECK)
            if diff > 0:
                actions.append(Action.CALL)
            if actor.chips > max(diff, 0) and opponent.chips > 0:
                actions.append(Action.RAISE)
            actions.append(Action.FOLD)

        return actions

    def get_max_raise(self) -> int:
        """Return the maximum raise amount the current actor can make.
        Cannot raise more than what the opponent can cover."""
        s = self.state
        actor = s.current_actor
        opponent = s.player1 if actor == s.player2 else s.player2
        diff = max(s.bet_to_match - actor.current_bet, 0)
        # Actor's chips minus what's needed to call
        actor_can_add = actor.chips - diff
        # Opponent's remaining chips is the cap
        max_raise = min(actor_can_add, opponent.chips)
        return max(max_raise, 1)  # minimum raise of 1

    def apply_action(self, action: Action, raise_amount: int = 1) -> str:
        """Apply a betting action. raise_amount is only used for RAISE. Returns a description string."""
        s = self.state
        actor = s.current_actor
        opponent = s.player1 if actor == s.player2 else s.player2

        if action == Action.FOLD:
            s.round_winner = opponent
            s.winner_reason = f"{actor.name} folded"
            s.phase = Phase.ROUND_OVER
            opponent.chips += s.pot
            s.pot = 0
            return f"{actor.name} folds!"

        elif action == Action.CHECK:
            msg = f"{actor.name} checks."
            # If both checked, move on
            if s.first_actor_checked:
                s.phase = Phase.SHOWDOWN
            else:
                s.first_actor_checked = True
                s.current_actor = opponent
            return msg

        elif action == Action.CALL:
            diff = s.bet_to_match - actor.current_bet
            actual = min(diff, actor.chips)
            actor.chips -= actual
            actor.current_bet += actual
            s.pot += actual
            msg = f"{actor.name} calls ({actual}b)."
            # Calling ends the betting round
            if s.phase == Phase.PRE_DRAW_BET:
                s.phase = Phase.DRAW
                s.draw_sub_phase = "follower_draw"
                s.current_actor = s.follower
            elif s.phase == Phase.POST_DRAW_BET:
                s.phase = Phase.SHOWDOWN
            return msg

        elif action == Action.RAISE:
            diff = s.bet_to_match - actor.current_bet
            # Clamp raise_amount between 1 and max_raise
            max_r = self.get_max_raise()
            raise_by = max(1, min(raise_amount, max_r))
            # Total to pay = call diff + the raise amount
            total = diff + raise_by
            actual = min(total, actor.chips)
            actor.chips -= actual
            actor.current_bet += actual
            s.pot += actual
            s.bet_to_match = actor.current_bet
            s.current_actor = opponent
            return f"{actor.name} raises by {raise_by}b (total bet: {actor.current_bet}b)!"

    def do_draw(self, player: Player, discard_indices: list[int]) -> int:
        """Player discards cards at given indices and draws replacements. Returns count discarded."""
        s = self.state
        discard_indices = sorted(discard_indices, reverse=True)
        discarded = []
        for idx in discard_indices:
            if 0 <= idx < len(player.hand):
                discarded.append(player.hand.pop(idx))

        s.discard_pile.extend(discarded)

        drawn = min(len(discarded), len(s.deck))
        for _ in range(drawn):
            player.hand.append(s.deck.pop())

        player.hand.sort(key=lambda c: c.value, reverse=True)
        return len(discarded)

    def advance_draw(self):
        """Move to the next draw sub-phase or to post-draw betting."""
        s = self.state
        if s.draw_sub_phase == "follower_draw":
            s.draw_sub_phase = "starter_draw"
            s.current_actor = s.starter
        elif s.draw_sub_phase == "starter_draw":
            # Move to post-draw betting
            s.phase = Phase.POST_DRAW_BET
            s.current_actor = s.starter  # S acts first in post-draw
            s.first_actor_checked = False
            # Reset bets for the new betting round
            s.player1.current_bet = 0
            s.player2.current_bet = 0
            s.bet_to_match = 0

    def swap_roles(self):
        s = self.state
        s.starter, s.follower = s.follower, s.starter

    def check_game_over(self) -> Optional[Player]:
        s = self.state
        if s.player1.chips <= 0:
            return s.player2
        if s.player2.chips <= 0:
            return s.player1
        return None
