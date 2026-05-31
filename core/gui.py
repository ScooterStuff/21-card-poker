"""
21 Card Poker — Tkinter GUI
A polished card-game interface.
"""

import tkinter as tk
from tkinter import font as tkfont
import time
import math

from .game_logic import (
    GameEngine, GameState, Player, Card, JOKER,
    Phase, Action, RANK_VALUES, SUITS,
)
from .hand_eval import evaluate_player_hand, determine_winner, HAND_NAMES
from .ai_player import AIPlayer


# ── Theme / Colors ────────────────────────────────────────────────

BG_COLOR = "#1a5c2a"         # Casino green
BG_DARK = "#144d22"
FELT_COLOR = "#1e7033"
CARD_BG = "#ffffff"
CARD_BACK = "#2b5797"
CARD_BACK_PATTERN = "#1e3d6b"
GOLD = "#f0c040"
GOLD_DARK = "#c89e30"
TEXT_LIGHT = "#f5f5f0"
TEXT_DIM = "#a0c0a8"
RED_SUIT = "#d32f2f"
BLACK_SUIT = "#1a1a1a"
BUTTON_BG = "#2b5797"
BUTTON_HOVER = "#3a6ab5"
BUTTON_TEXT = "#ffffff"
CHIP_GOLD = "#f5d060"
CHIP_BORDER = "#b8960a"
POT_COLOR = "#e8c840"
FOLD_RED = "#c0392b"
CHECK_GREEN = "#27ae60"
RAISE_ORANGE = "#e67e22"
CARD_SHADOW = "#0d3015"
SELECTED_GLOW = "#ffeb3b"
DISABLED_BTN = "#5a7a5f"
JOKER_PURPLE = "#9b59b6"

CARD_WIDTH = 80
CARD_HEIGHT = 115
CARD_RADIUS = 10
CARD_GAP = 10


class PokerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("21 Card Poker")
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(True, True)

        # Try to set a reasonable window size
        self.root.geometry("1000x750")
        self.root.minsize(850, 650)

        # Fonts
        self.font_title = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self.font_large = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        self.font_medium = tkfont.Font(family="Segoe UI", size=12)
        self.font_medium_bold = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        self.font_small = tkfont.Font(family="Segoe UI", size=10)
        self.font_card_rank = tkfont.Font(family="Segoe UI", size=16, weight="bold")
        self.font_card_suit = tkfont.Font(family="Segoe UI", size=22)
        self.font_card_small = tkfont.Font(family="Segoe UI", size=9)
        self.font_button = tkfont.Font(family="Segoe UI", size=12, weight="bold")
        self.font_chip = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.font_joker = tkfont.Font(family="Segoe UI", size=14, weight="bold")

        # Game engine
        self.engine = GameEngine(base_bet=1, starting_chips=50)
        self.ai = AIPlayer()
        self.state: GameState = None

        # GUI state
        self.selected_cards: set[int] = set()  # indices of cards selected for discard
        self.card_widgets: list = []
        self.ai_card_widgets: list = []
        self.show_ai_cards = False
        self.action_after_id = None

        self._build_ui()
        self._show_start_screen()

    # ── UI Construction ───────────────────────────────────────────

    def _build_ui(self):
        # Main container
        self.main_frame = tk.Frame(self.root, bg=BG_COLOR)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top bar: opponent info
        self.top_bar = tk.Frame(self.main_frame, bg=BG_DARK, height=60)
        self.top_bar.pack(fill=tk.X, pady=(0, 5))
        self.top_bar.pack_propagate(False)

        self.ai_name_label = tk.Label(
            self.top_bar, text="🤖 Opponent", font=self.font_large,
            bg=BG_DARK, fg=TEXT_LIGHT, anchor="w"
        )
        self.ai_name_label.pack(side=tk.LEFT, padx=15, pady=10)

        self.ai_chips_label = tk.Label(
            self.top_bar, text="Chips: 50b", font=self.font_medium_bold,
            bg=BG_DARK, fg=CHIP_GOLD, anchor="e"
        )
        self.ai_chips_label.pack(side=tk.RIGHT, padx=15, pady=10)

        self.ai_role_label = tk.Label(
            self.top_bar, text="", font=self.font_small,
            bg=BG_DARK, fg=TEXT_DIM
        )
        self.ai_role_label.pack(side=tk.RIGHT, padx=10, pady=10)

        self.ai_discard_label = tk.Label(
            self.top_bar, text="", font=self.font_small,
            bg=BG_DARK, fg=TEXT_DIM
        )
        self.ai_discard_label.pack(side=tk.RIGHT, padx=5, pady=10)

        # AI cards area
        self.ai_cards_frame = tk.Frame(self.main_frame, bg=BG_COLOR, height=140)
        self.ai_cards_frame.pack(fill=tk.X, pady=(5, 5))

        self.ai_cards_inner = tk.Frame(self.ai_cards_frame, bg=BG_COLOR)
        self.ai_cards_inner.pack(expand=True)

        # Center area: pot, phase info, messages
        self.center_frame = tk.Frame(self.main_frame, bg=FELT_COLOR, height=140)
        self.center_frame.pack(fill=tk.X, pady=5)
        self.center_frame.pack_propagate(False)

        self.round_label = tk.Label(
            self.center_frame, text="", font=self.font_medium_bold,
            bg=FELT_COLOR, fg=TEXT_LIGHT
        )
        self.round_label.pack(pady=(10, 2))

        self.pot_label = tk.Label(
            self.center_frame, text="Pot: 0b", font=self.font_large,
            bg=FELT_COLOR, fg=POT_COLOR
        )
        self.pot_label.pack(pady=(2, 2))

        self.phase_label = tk.Label(
            self.center_frame, text="", font=self.font_medium,
            bg=FELT_COLOR, fg=TEXT_LIGHT
        )
        self.phase_label.pack(pady=(2, 2))

        self.message_label = tk.Label(
            self.center_frame, text="", font=self.font_medium_bold,
            bg=FELT_COLOR, fg=GOLD, wraplength=700
        )
        self.message_label.pack(pady=(2, 8))

        # Player cards area
        self.player_cards_frame = tk.Frame(self.main_frame, bg=BG_COLOR, height=150)
        self.player_cards_frame.pack(fill=tk.X, pady=(5, 5))

        self.player_cards_inner = tk.Frame(self.player_cards_frame, bg=BG_COLOR)
        self.player_cards_inner.pack(expand=True)

        # Hand evaluation display
        self.hand_eval_label = tk.Label(
            self.main_frame, text="", font=self.font_medium,
            bg=BG_COLOR, fg=GOLD
        )
        self.hand_eval_label.pack(pady=(0, 5))

        # Bottom bar: player info + action buttons
        self.bottom_bar = tk.Frame(self.main_frame, bg=BG_DARK, height=110)
        self.bottom_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
        self.bottom_bar.pack_propagate(False)

        # Player info row
        info_row = tk.Frame(self.bottom_bar, bg=BG_DARK)
        info_row.pack(fill=tk.X, padx=15, pady=(8, 2))

        self.player_name_label = tk.Label(
            info_row, text="👤 You", font=self.font_large,
            bg=BG_DARK, fg=TEXT_LIGHT, anchor="w"
        )
        self.player_name_label.pack(side=tk.LEFT)

        self.player_chips_label = tk.Label(
            info_row, text="Chips: 50b", font=self.font_medium_bold,
            bg=BG_DARK, fg=CHIP_GOLD, anchor="e"
        )
        self.player_chips_label.pack(side=tk.RIGHT)

        self.player_role_label = tk.Label(
            info_row, text="", font=self.font_small,
            bg=BG_DARK, fg=TEXT_DIM
        )
        self.player_role_label.pack(side=tk.RIGHT, padx=10)

        # Action buttons row
        self.btn_frame = tk.Frame(self.bottom_bar, bg=BG_DARK)
        self.btn_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        self.buttons: dict[str, tk.Button] = {}
        self._action_buttons = []

        # Raise controls (slider + entry) — created once, shown/hidden as needed
        self.raise_frame = tk.Frame(self.bottom_bar, bg=BG_DARK)
        self.raise_var = tk.IntVar(value=1)
        self.raise_slider = tk.Scale(
            self.raise_frame, from_=1, to=50, orient=tk.HORIZONTAL,
            variable=self.raise_var, bg=BG_DARK, fg=GOLD, troughcolor=FELT_COLOR,
            highlightthickness=0, length=250, font=self.font_small,
            activebackground=RAISE_ORANGE, label="Raise amount:",
            sliderlength=20
        )
        self.raise_slider.pack(side=tk.LEFT, padx=(0, 8))
        self.raise_confirm_btn = tk.Button(
            self.raise_frame, text="✅ Confirm Raise", font=self.font_button,
            bg=RAISE_ORANGE, fg=BUTTON_TEXT, activebackground="#f39c12",
            relief=tk.FLAT, padx=14, pady=4, cursor="hand2",
            command=self._confirm_raise, bd=0, highlightthickness=0
        )
        self.raise_confirm_btn.pack(side=tk.LEFT, padx=5)
        self.raise_cancel_btn = tk.Button(
            self.raise_frame, text="↩ Cancel", font=self.font_button,
            bg="#555", fg=BUTTON_TEXT, activebackground="#777",
            relief=tk.FLAT, padx=14, pady=4, cursor="hand2",
            command=self._cancel_raise, bd=0, highlightthickness=0
        )
        self.raise_cancel_btn.pack(side=tk.LEFT, padx=5)

    def _clear_buttons(self):
        for w in self._action_buttons:
            w.destroy()
        self._action_buttons = []
        self.buttons = {}

    def _add_button(self, text: str, command, color=BUTTON_BG, hover=BUTTON_HOVER,
                    fg=BUTTON_TEXT, side=tk.LEFT):
        btn = tk.Button(
            self.btn_frame, text=text, font=self.font_button,
            bg=color, fg=fg, activebackground=hover, activeforeground=fg,
            relief=tk.FLAT, padx=20, pady=6, cursor="hand2",
            command=command, bd=0, highlightthickness=0
        )
        btn.pack(side=side, padx=5)
        # Hover effect
        btn.bind("<Enter>", lambda e, b=btn, h=hover: b.configure(bg=h))
        btn.bind("<Leave>", lambda e, b=btn, c=color: b.configure(bg=c))
        self._action_buttons.append(btn)
        self.buttons[text] = btn
        return btn

    # ── Card Rendering ────────────────────────────────────────────

    def _create_card_face(self, parent, card: Card, idx: int = -1,
                          clickable: bool = False, selected: bool = False,
                          small: bool = False) -> tk.Canvas:
        w = CARD_WIDTH if not small else 65
        h = CARD_HEIGHT if not small else 95
        c = tk.Canvas(parent, width=w, height=h, bg=BG_COLOR,
                      highlightthickness=0, bd=0)

        # Card shadow
        c.create_rectangle(3, 3, w, h, fill=CARD_SHADOW, outline="", width=0)

        # Selection glow
        outline_color = SELECTED_GLOW if selected else "#888888"
        outline_width = 3 if selected else 1

        # Card body (rounded rect via polygon)
        r = CARD_RADIUS
        c.create_rectangle(0, 0, w - 3, h - 3, fill=CARD_BG,
                           outline=outline_color, width=outline_width)

        if card.is_joker:
            # Joker card
            c.create_text(w // 2 - 1, h // 2 - 15, text="🃏",
                          font=self.font_card_suit, fill=JOKER_PURPLE)
            c.create_text(w // 2 - 1, h // 2 + 15, text="JOKER",
                          font=self.font_card_small, fill=JOKER_PURPLE)
        else:
            # Color
            color = RED_SUIT if card.suit in ("♥", "♦") else BLACK_SUIT

            # Top-left rank + suit
            fnt_r = self.font_card_rank if not small else self.font_card_small
            fnt_s = self.font_card_suit if not small else self.font_medium
            c.create_text(12, 14 if not small else 12, text=card.rank,
                          font=fnt_r, fill=color, anchor="center")
            c.create_text(12, 32 if not small else 26, text=card.suit,
                          font=fnt_s if not small else self.font_small,
                          fill=color, anchor="center")

            # Center suit (large)
            c.create_text(w // 2 - 1, h // 2, text=card.suit,
                          font=tkfont.Font(family="Segoe UI", size=28 if not small else 20),
                          fill=color)

            # Bottom-right (inverted)
            c.create_text(w - 14, h - 17 if not small else h - 14, text=card.rank,
                          font=fnt_r, fill=color, anchor="center")

        if clickable and idx >= 0:
            c.bind("<Button-1>", lambda e, i=idx: self._toggle_card(i))
            c.configure(cursor="hand2")

        return c

    def _create_card_back(self, parent, small=False) -> tk.Canvas:
        w = CARD_WIDTH if not small else 65
        h = CARD_HEIGHT if not small else 95
        c = tk.Canvas(parent, width=w, height=h, bg=BG_COLOR,
                      highlightthickness=0, bd=0)
        c.create_rectangle(3, 3, w, h, fill=CARD_SHADOW, outline="", width=0)
        c.create_rectangle(0, 0, w - 3, h - 3, fill=CARD_BACK, outline="#1a3557", width=2)
        # Pattern
        margin = 6
        c.create_rectangle(margin, margin, w - 3 - margin, h - 3 - margin,
                           fill=CARD_BACK_PATTERN, outline=CARD_BACK, width=1)
        # Diamond pattern
        cx, cy = (w - 3) // 2, (h - 3) // 2
        size = 12 if not small else 8
        c.create_polygon(cx, cy - size, cx + size, cy, cx, cy + size, cx - size, cy,
                         fill=GOLD, outline=GOLD_DARK, width=1)
        return c

    # ── Display Updates ───────────────────────────────────────────

    def _render_ai_cards(self):
        for w in self.ai_cards_inner.winfo_children():
            w.destroy()

        if self.state is None:
            return

        hand = self.state.player2.hand
        for i, card in enumerate(hand):
            if self.show_ai_cards:
                cw = self._create_card_face(self.ai_cards_inner, card, small=False)
            else:
                cw = self._create_card_back(self.ai_cards_inner, small=False)
            cw.pack(side=tk.LEFT, padx=4)

    def _render_player_cards(self, clickable=False):
        for w in self.player_cards_inner.winfo_children():
            w.destroy()

        if self.state is None:
            return

        hand = self.state.player1.hand
        for i, card in enumerate(hand):
            selected = i in self.selected_cards
            cw = self._create_card_face(
                self.player_cards_inner, card, idx=i,
                clickable=clickable, selected=selected
            )
            cw.pack(side=tk.LEFT, padx=4)

        # Update hand eval
        if hand:
            score, name, joker = evaluate_player_hand(hand)
            self.hand_eval_label.config(text=f"Your hand: {name}")
        else:
            self.hand_eval_label.config(text="")

    def _update_info(self):
        s = self.state
        if s is None:
            return

        self.player_chips_label.config(text=f"Chips: {s.player1.chips}b")
        self.ai_chips_label.config(text=f"Chips: {s.player2.chips}b")
        self.pot_label.config(text=f"💰 Pot: {s.pot}b")
        self.round_label.config(text=f"Round {s.round_number}")

        # Role labels
        if s.starter == s.player1:
            self.player_role_label.config(text="[Starter]")
            self.ai_role_label.config(text="[Follower]")
        else:
            self.player_role_label.config(text="[Follower]")
            self.ai_role_label.config(text="[Starter]")

        # Discard info
        if s.follower_discarded >= 0 and s.follower == s.player2:
            self.ai_discard_label.config(text=f"Discarded: {s.follower_discarded}")
        elif s.starter_discarded >= 0 and s.starter == s.player2:
            self.ai_discard_label.config(text=f"Discarded: {s.starter_discarded}")
        else:
            self.ai_discard_label.config(text="")

    def _update_phase_display(self):
        s = self.state
        if s is None:
            return

        phase_names = {
            Phase.PRE_DRAW_BET: "Pre-Draw Betting",
            Phase.DRAW: "Draw Phase",
            Phase.POST_DRAW_BET: "Post-Draw Betting",
            Phase.SHOWDOWN: "Showdown!",
            Phase.ROUND_OVER: "Round Over",
            Phase.GAME_OVER: "Game Over",
        }
        self.phase_label.config(text=phase_names.get(s.phase, ""))

    def _set_message(self, text: str, color=GOLD):
        self.message_label.config(text=text, fg=color)

    # ── Start Screen ──────────────────────────────────────────────

    def _show_start_screen(self):
        self._clear_buttons()
        self.hand_eval_label.config(text="")
        self.pot_label.config(text="")
        self.round_label.config(text="")
        self.phase_label.config(text="")
        self.player_chips_label.config(text="")
        self.ai_chips_label.config(text="")
        self.player_role_label.config(text="")
        self.ai_role_label.config(text="")
        self.ai_discard_label.config(text="")
        self.ai_name_label.config(text="🤖 Opponent")
        self.player_name_label.config(text="👤 You")

        for w in self.player_cards_inner.winfo_children():
            w.destroy()
        for w in self.ai_cards_inner.winfo_children():
            w.destroy()

        self._set_message("♠ ♥ 21 Card Poker ♦ ♣", GOLD)
        self.phase_label.config(text="2 Player • Joker Wild • Draw Poker")

        self._add_button("🎮  New Game", self._start_game, color="#27ae60", hover="#2ecc71")

    # ── Game Flow ─────────────────────────────────────────────────

    def _start_game(self):
        self.state = self.engine.new_game()
        self._start_round()

    def _start_round(self):
        s = self.state
        self.show_ai_cards = False
        self.selected_cards = set()
        self.engine.start_round()
        self._update_info()
        self._update_phase_display()
        self._render_ai_cards()
        self._render_player_cards()

        self._set_message(
            f"Forced bets placed. S={s.starter.name} (2b), F={s.follower.name} (1b)."
        )

        # A small delay then start betting
        self.root.after(800, self._advance_game)

    def _advance_game(self):
        """Main game loop driver — checks phase and routes to correct handler."""
        s = self.state
        self._update_info()
        self._update_phase_display()

        if s.phase == Phase.PRE_DRAW_BET or s.phase == Phase.POST_DRAW_BET:
            self._handle_betting()
        elif s.phase == Phase.DRAW:
            self._handle_draw()
        elif s.phase == Phase.SHOWDOWN:
            self._handle_showdown()
        elif s.phase == Phase.ROUND_OVER:
            self._handle_round_over()
        elif s.phase == Phase.GAME_OVER:
            self._handle_game_over()

    def _handle_betting(self):
        s = self.state
        available = self.engine.get_available_actions()

        if s.current_actor == s.player2:
            # AI's turn
            self._set_message("Opponent is thinking...", TEXT_DIM)
            self._clear_buttons()
            self._render_player_cards(clickable=False)
            self.root.after(800, lambda: self._ai_bet(available))
        else:
            # Human's turn
            phase_name = "Pre-Draw" if s.phase == Phase.PRE_DRAW_BET else "Post-Draw"
            self._set_message(f"{phase_name} Betting — Your turn!", TEXT_LIGHT)
            self._show_bet_buttons(available)
            self._render_player_cards(clickable=False)

    def _show_bet_buttons(self, available: list[Action]):
        self._clear_buttons()
        self._hide_raise_slider()
        self._cached_available = available  # store for re-show after cancel
        for action in available:
            if action == Action.FOLD:
                self._add_button("❌ Fold", lambda: self._human_bet(Action.FOLD),
                                 color=FOLD_RED, hover="#e74c3c")
            elif action == Action.CHECK:
                self._add_button("✋ Check", lambda: self._human_bet(Action.CHECK),
                                 color=CHECK_GREEN, hover="#2ecc71")
            elif action == Action.CALL:
                diff = self.state.bet_to_match - self.state.player1.current_bet
                self._add_button(f"📞 Call ({diff}b)", lambda: self._human_bet(Action.CALL),
                                 color=BUTTON_BG, hover=BUTTON_HOVER)
            elif action == Action.RAISE:
                self._add_button("⬆ Raise...", self._show_raise_slider,
                                 color=RAISE_ORANGE, hover="#f39c12")

    def _show_raise_slider(self):
        """Show the raise amount slider."""
        max_raise = self.engine.get_max_raise()
        self.raise_slider.configure(from_=1, to=max_raise)
        self.raise_var.set(1)
        self._clear_buttons()
        self.raise_frame.pack(fill=tk.X, padx=15, pady=(0, 8), before=self.btn_frame)
        diff = self.state.bet_to_match - self.state.player1.current_bet
        self._set_message(f"Choose raise amount (1b – {max_raise}b). Call cost: {max(diff,0)}b + your raise.", TEXT_LIGHT)

    def _hide_raise_slider(self):
        self.raise_frame.pack_forget()

    def _confirm_raise(self):
        amount = self.raise_var.get()
        self._hide_raise_slider()
        self._human_bet(Action.RAISE, raise_amount=amount)

    def _cancel_raise(self):
        self._hide_raise_slider()
        if hasattr(self, '_cached_available'):
            self._show_bet_buttons(self._cached_available)

    def _human_bet(self, action: Action, raise_amount: int = 1):
        msg = self.engine.apply_action(action, raise_amount=raise_amount)
        self._set_message(msg)
        self._update_info()
        self.root.after(600, self._advance_game)

    def _ai_bet(self, available):
        action, raise_amt = self.ai.choose_action(self.state, available)
        msg = self.engine.apply_action(action, raise_amount=raise_amt)
        self._set_message(msg)
        self._update_info()
        self.root.after(600, self._advance_game)

    # ── Draw Phase ────────────────────────────────────────────────

    def _handle_draw(self):
        s = self.state

        if s.draw_sub_phase == "follower_draw":
            if s.follower == s.player1:
                self._human_draw_prompt()
            else:
                self._ai_draw()
        elif s.draw_sub_phase == "starter_draw":
            if s.starter == s.player1:
                self._human_draw_prompt()
            else:
                self._ai_draw()

    def _human_draw_prompt(self):
        self.selected_cards = set()
        self._set_message("Click cards to select for discard, then confirm. (0-5 cards)", TEXT_LIGHT)
        self._render_player_cards(clickable=True)
        self._clear_buttons()
        self._add_button("✅ Confirm Discard", self._human_discard_confirm,
                         color=CHECK_GREEN, hover="#2ecc71")

    def _toggle_card(self, idx: int):
        if idx in self.selected_cards:
            self.selected_cards.discard(idx)
        else:
            self.selected_cards.add(idx)
        self._render_player_cards(clickable=True)
        count = len(self.selected_cards)
        self._set_message(f"Selected {count} card(s) to discard. Click Confirm when ready.", TEXT_LIGHT)

    def _human_discard_confirm(self):
        s = self.state
        indices = sorted(self.selected_cards)
        count = self.engine.do_draw(s.player1, indices)

        if s.draw_sub_phase == "follower_draw":
            s.follower_discarded = count
        else:
            s.starter_discarded = count

        self.selected_cards = set()
        self._set_message(f"You discarded {count} card(s) and drew replacements.")
        self._render_player_cards(clickable=False)
        self._render_ai_cards()
        self._update_info()

        self.engine.advance_draw()
        self.root.after(600, self._advance_game)

    def _ai_draw(self):
        s = self.state
        self._set_message("Opponent is choosing cards to discard...", TEXT_DIM)
        self._clear_buttons()

        def do_ai_draw():
            indices = self.ai.choose_discards(s)
            count = self.engine.do_draw(s.player2, indices)

            if s.draw_sub_phase == "follower_draw":
                s.follower_discarded = count
            else:
                s.starter_discarded = count

            self._set_message(f"Opponent discarded {count} card(s).")
            self._render_ai_cards()
            self._update_info()
            self.engine.advance_draw()
            self.root.after(600, self._advance_game)

        self.root.after(800, do_ai_draw)

    # ── Showdown ──────────────────────────────────────────────────

    def _handle_showdown(self):
        s = self.state
        self.show_ai_cards = True
        self._render_ai_cards()
        self._render_player_cards(clickable=False)
        self._clear_buttons()

        result, name1, name2, joker1, joker2 = determine_winner(
            s.player1.hand, s.player2.hand
        )

        joker_text = ""
        if joker1:
            joker_text += f"  |  Your Joker → {joker1}"
            s.joker_resolved_as = joker1
        if joker2:
            joker_text += f"  |  Opponent's Joker → {joker2}"

        if result > 0:
            s.round_winner = s.player1
            s.player1.chips += s.pot
            s.winner_reason = f"You win with {name1}!  (Opponent: {name2}){joker_text}"
            self._set_message(f"🎉 {s.winner_reason}", "#2ecc71")
        elif result < 0:
            s.round_winner = s.player2
            s.player2.chips += s.pot
            s.winner_reason = f"Opponent wins with {name2}!  (You: {name1}){joker_text}"
            self._set_message(f"😔 {s.winner_reason}", FOLD_RED)
        else:
            # Tie — split pot
            half = s.pot // 2
            s.player1.chips += half
            s.player2.chips += s.pot - half
            s.winner_reason = f"Tie! Both have {name1}. Pot split.{joker_text}"
            self._set_message(f"🤝 {s.winner_reason}", GOLD)

        s.pot = 0
        self._update_info()

        # Check game over
        game_winner = self.engine.check_game_over()
        if game_winner:
            s.phase = Phase.GAME_OVER
            self.root.after(2000, self._handle_game_over)
        else:
            s.phase = Phase.ROUND_OVER
            self._add_button("▶  Next Round", self._next_round,
                             color=CHECK_GREEN, hover="#2ecc71")

    def _handle_round_over(self):
        # This is called if we get here via advance_game (fold scenario)
        s = self.state
        self._clear_buttons()
        self._update_info()

        if s.round_winner:
            winner_name = s.round_winner.name
            self._set_message(f"{winner_name} wins the pot! ({s.winner_reason})", GOLD)

        game_winner = self.engine.check_game_over()
        if game_winner:
            s.phase = Phase.GAME_OVER
            self.root.after(1500, self._handle_game_over)
        else:
            self._add_button("▶  Next Round", self._next_round,
                             color=CHECK_GREEN, hover="#2ecc71")

    def _next_round(self):
        self.engine.swap_roles()
        self._start_round()

    def _handle_game_over(self):
        s = self.state
        self._clear_buttons()
        self._update_info()

        if s.player1.chips <= 0:
            self._set_message("💀 GAME OVER — You ran out of chips! Opponent wins!", FOLD_RED)
        elif s.player2.chips <= 0:
            self._set_message("🏆 GAME OVER — Opponent ran out of chips! You win!", "#2ecc71")
        else:
            if s.player1.chips > s.player2.chips:
                self._set_message(f"🏆 GAME OVER — You win! ({s.player1.chips}b vs {s.player2.chips}b)", "#2ecc71")
            elif s.player2.chips > s.player1.chips:
                self._set_message(f"💀 GAME OVER — Opponent wins! ({s.player2.chips}b vs {s.player1.chips}b)", FOLD_RED)
            else:
                self._set_message(f"🤝 GAME OVER — Tie! Both have {s.player1.chips}b", GOLD)

        self._add_button("🎮  Play Again", self._restart_game,
                         color="#27ae60", hover="#2ecc71")

    def _restart_game(self):
        self.state = self.engine.new_game()
        self.show_ai_cards = False
        self.selected_cards = set()
        self._start_round()


def main():
    root = tk.Tk()
    app = PokerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
