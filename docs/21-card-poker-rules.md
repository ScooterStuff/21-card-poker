# 21 Card Poker — Game Rules & Implementation Spec

## Deck

- 20 standard cards: Ace, King, Queen, Jack, 10 in all 4 suits (♠ ♥ ♦ ♣)
- 1 Joker (wild card) — at showdown it becomes whichever of the 20 cards produces the highest hand for its holder
- **Total: 21 cards**

## Players & Roles

- 2 players. Each round one is **Starter (S)** and the other is **Follower (F)**.
- Roles swap every round.

## Chips

- Each player starts with **50b** chips (b = base bet unit, configurable).
- All bets/raises are in increments of **1b** (minimum raise is 1b, but you may raise by any amount).

## Round Flow

### Turn 0 — Forced Bets & Deal

1. S places **2b** into the pot.
2. F places **1b** into the pot.
3. Shuffle the 21-card deck. Deal **5 cards** to each player face-down. 11 cards remain as the draw pile.

### Turn 1 — Pre-Draw Betting (F acts first)

- F must match S's 2b to stay in, so F's minimum action is **Call** (add 1b).
- Available actions for the acting player: **Call**, **Raise** (any amount ≥ 1b above current bet, up to opponent's remaining chips), **Fold** (forfeit pot).
- After a call with no raise, the betting round ends. After a raise, action passes to the opponent who can call, re-raise, or fold.
- **No raise cap** — you may raise/re-raise as long as you have chips, but you cannot raise more than the opponent can cover.
- If a player folds, the round ends immediately and the opponent wins the pot.

### Turn 2 — Draw Phase

1. **F discards first**: chooses 0–5 cards from their hand, discards them face-down, draws that many from the draw pile.
2. **S is told how many cards F discarded** (not which cards).
3. **S discards second**: chooses 0–5 cards, discards face-down, draws replacements.
4. **F is told how many cards S discarded** (not which cards).

- Discarded cards are removed from play permanently (not reshuffled).

### Turn 3 — Post-Draw Betting (S acts first)

- Same rules as Turn 1 betting but **S acts first**.
- Available actions: **Check** (pass with no bet, only if no bet is outstanding), **Raise** (any amount ≥ 1b, up to opponent's remaining chips), **Call**, **Fold**.
- **No raise cap** — same rules as Turn 1.
- If both players check, proceed to showdown.

### Showdown

- Both players reveal hands. Joker is resolved to the best possible card.
- Higher-ranking hand wins the entire pot.
- Exact tie: pot is split evenly.
- Swap roles and start next round.

## Hand Rankings (High to Low)

| Rank | Hand                | Description                                            |
| ---- | ------------------- | ------------------------------------------------------ |
| 1    | **Five of a Kind**  | Four of one rank + Joker (e.g., A♠A♥A♦A♣ + Joker)      |
| 2    | **Royal Flush**     | A-K-Q-J-10 all same suit                               |
| 3    | **Four of a Kind**  | Four cards of same rank + one kicker                   |
| 4    | **Full House**      | Three of a kind + a pair                               |
| 5    | **Straight**        | A-K-Q-J-10 of mixed suits (the only possible straight) |
| 6    | **Three of a Kind** | Three cards of same rank + two unrelated cards         |
| 7    | **Two Pair**        | Two different pairs + one kicker                       |
| 8    | **Pair**            | One pair + three unrelated cards                       |

**Notes:**

- High Card is impossible — with 5 cards from only 5 ranks, you always have at least a pair (pigeonhole principle).
- Flush and Straight Flush don't exist as separate categories — any 5 suited cards from this deck must be A-K-Q-J-10, which is a Royal Flush.
- Five of a Kind is only possible with the Joker.
- The only possible straight is A-K-Q-J-10.

**Tiebreakers (compare in order):**

- Four/Three of a Kind & Pair: higher set rank wins, then compare kickers highest to lowest.
- Full House: higher trips rank, then higher pair rank.
- Two Pair: higher pair, then lower pair, then kicker.
- Pair: higher pair rank, then kickers highest to lowest.
- Straight vs Straight: always ties (only one straight exists).
- **Card rank order: Ace > King > Queen > Jack > 10.**

## Joker Resolution

At showdown, evaluate the Joker holder's hand with the Joker substituted as each of the 20 possible cards (every rank-suit combination). Use whichever produces the highest-ranking hand. Display the resolved identity at showdown.

## Game End

- A player runs out of chips — opponent wins.
- Or an agreed number of rounds is reached — most chips wins.
- If a player cannot cover forced bets, they go all-in with remaining chips. The opponent can only win up to the all-in amount; excess is returned.
