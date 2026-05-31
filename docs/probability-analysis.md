# 21 Card Poker — Pre-Discard Win Probability Analysis

## Objective

Given a **starting 5-card hand** (before the draw phase), calculate the **probability of winning at showdown** against all possible opponent hands — assuming **no draws occur** (i.e. both players keep their dealt cards).

This answers the question: _"If I'm dealt hand H₁, how likely am I to beat a random opponent hand H₂?"_

## Why Pre-Discard?

At Turn 1 (Pre-Draw Betting), a player must decide whether to Call, Raise, or Fold **before** seeing any draw. The pre-discard win probability tells you the **raw strength** of your starting hand against the full distribution of opponent hands. It is the foundation for optimal pre-draw betting decisions.

## Methodology

### Deck & Combinatorics

| Quantity                   | Value                            |
| -------------------------- | -------------------------------- |
| Deck size                  | 21 cards (20 standard + 1 Joker) |
| Possible 5-card hands      | C(21, 5) = **20,349**            |
| Opponent hands given H₁    | C(16, 5) = **4,368**             |
| Total pairwise comparisons | 20,349 × 4,368 = **88,884,432**  |

### Card Exclusion Constraint

Once you hold a hand H₁ of 5 specific cards, those cards are **removed** from the pool. The opponent's hand H₂ is drawn from the **remaining 16 cards**. This means:

- If you hold 3 Aces, only 1 Ace remains for the opponent.
- If you hold the Joker, the opponent **cannot** have it.
- The opponent's hand distribution shifts based on exactly which cards you hold.

### Joker Handling

The Joker is a **wild card** that becomes whichever of the 20 standard cards produces the **highest-ranking hand** for its holder. At evaluation time:

- If a hand contains the Joker, all 20 possible substitutions (5 ranks × 4 suits) are tested.
- The substitution producing the best hand ranking (with tiebreakers) is used.
- This means the Joker's power is **context-dependent** — it's most valuable when it completes a Four of a Kind → Five of a Kind, or fills a missing card for a Royal Flush.

### Evaluation Steps

For each of the 20,349 possible starting hands H₁:

1. **Evaluate H₁** — determine its hand rank (Royal Flush through Pair) and tiebreaker values. Resolve Joker if present.
2. **Enumerate all opponent hands H₂** — all C(16, 5) = 4,368 combinations from the 16 remaining cards.
3. **Evaluate each H₂** — same hand evaluation with Joker resolution.
4. **Compare H₁ vs H₂** — determine win, loss, or tie for each matchup.
5. **Compute probabilities:**
   - Win % = wins / 4,368 × 100
   - Loss % = losses / 4,368 × 100
   - Tie % = ties / 4,368 × 100

### Hand Ranking (for reference)

| Rank      | Hand            | Key                     |
| --------- | --------------- | ----------------------- |
| 1 (best)  | Five of a Kind  | 4 of a rank + Joker     |
| 2         | Royal Flush     | A-K-Q-J-10, same suit   |
| 3         | Four of a Kind  | 4 of same rank + kicker |
| 4         | Full House      | Trips + pair            |
| 5         | Straight        | A-K-Q-J-10, mixed suits |
| 6         | Three of a Kind | Trips + 2 kickers       |
| 7         | Two Pair        | 2 pairs + kicker        |
| 8 (worst) | Pair            | 1 pair + 3 kickers      |

Tiebreakers apply within the same rank (higher card values win). Card values: A(5) > K(4) > Q(3) > J(2) > 10(1).

## Output

The calculator produces two files:

### `hand_probabilities.csv` — Full Results (20,349 rows)

Each row is one possible 5-card starting hand, with columns:

| Column               | Description                                   |
| -------------------- | --------------------------------------------- |
| Rank                 | Overall rank by win % (1 = best hand)         |
| Hand                 | The 5 cards (e.g. "A♠ A♥ A♦ A♣ 🃏")           |
| Hand Type            | Category name (e.g. "Five of a Kind")         |
| Win %                | Probability of beating a random opponent hand |
| Loss %               | Probability of losing                         |
| Tie %                | Probability of tying                          |
| Wins / Losses / Ties | Raw counts out of 4,368 matchups              |

### `hand_type_summary.csv` — Summary by Category

Aggregate statistics for each hand category (Royal Flush, Five of a Kind, etc.), including:

- Count of hands in that category
- Average win/loss/tie percentages
- Min and max win % within the category

## Key Insights to Look For

- **Joker hands vs non-Joker hands**: How much does holding the Joker boost win probability?
- **Best and worst starting hands**: Which specific 5-card combos win the most/least?
- **Hand type strength overlap**: Does the best Two Pair beat the worst Three of a Kind?
- **Suit effects**: For non-flush hands, do suits matter at all? (They shouldn't, except through Joker resolution.)

## Usage

```bash
python probability_calculator.py
```

Runtime: approximately 2–10 minutes depending on hardware (88.9M comparisons).
