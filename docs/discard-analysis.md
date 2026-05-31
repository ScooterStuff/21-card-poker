# 21 Card Poker — Draw Phase (Turn 2) Optimal Discard Analysis

## Objective

Given a **starting 5-card hand** (after the deal, before the draw), determine the **optimal discard strategy** — i.e. which subset of cards to discard and replace to **maximize expected win probability** at showdown.

This answers the question: _"Given my hand, which cards (if any) should I throw away and redraw to give myself the best chance of winning?"_

## Context: When This Decision Happens

```
Turn 0: Deal → you receive 5 cards, 11 remain in draw pile, opponent has 5
Turn 1: Pre-draw betting
Turn 2: DRAW PHASE ← this analysis
  └─ You choose 0–5 cards to discard, draw replacements from the pile
Turn 3: Post-draw betting
Showdown
```

At the moment of the discard decision, you know:

- **Your 5 cards** (known)
- **Opponent's hand** (unknown — 5 of the remaining 16 cards)
- **Draw pile** (unknown — 11 of the remaining 16 cards)
- You do **not** know how the 16 remaining cards are split between opponent and draw pile

## Discard Options

For any 5-card hand, the possible discard choices are all subsets of the hand:

| Cards Discarded (k) | Number of Ways | Notation                         |
| ------------------- | -------------- | -------------------------------- |
| 0 (keep all)        | C(5,0) = 1     | —                                |
| 1                   | C(5,1) = 5     | discard card at position i       |
| 2                   | C(5,2) = 10    | discard cards at positions i,j   |
| 3                   | C(5,3) = 10    | discard cards at positions i,j,k |
| 4                   | C(5,4) = 5     | keep only card at position i     |
| 5                   | C(5,5) = 1     | discard entire hand              |
| **Total**           | **32**         | all subsets of a 5-element set   |

## What Happens After You Discard

When you discard k cards:

1. Those k cards are **permanently removed** from play (they cannot appear in opponent's hand or future draws).
2. You draw k replacement cards from the **draw pile** (11 cards).
3. Your new hand = (5 − k) kept cards + k drawn cards.
4. The opponent still holds their original 5 cards (unchanged by your draw).

## Card Pool & Exclusion Logic

This is where the analysis gets subtle. At discard time:

- **21 total cards** in the game
- **5 cards in your hand** (known to you)
- **16 remaining cards** (unknown to you), split as:
  - 5 in opponent's hand
  - 11 in draw pile

### After you discard k cards and draw k replacements:

- Your **discarded k cards** are out of play → they are NOT in the opponent's hand (were never dealt to opponent) and NOT in the draw pile anymore
- The **k cards you drew** came from the draw pile → they are also NOT in the opponent's hand
- So the opponent's 5 cards must come from: the 16 remaining cards **minus** the k you drew = **(16 − k) cards**

### Probability model

For a given discard choice of k cards:

1. The 16 unknown cards must be partitioned into:
   - **k cards for your draw** (from the 11-card draw pile)
   - **5 cards for the opponent** (dealt before your draw)
   - **11 − k cards** remaining unused in the draw pile

2. Not all partitions are equally likely in isolation, but since both the deal and draw pile are random, we model this as:
   - Choose k cards to draw from the 16 remaining: **C(16, k)** ways
   - Choose 5 cards for opponent from the other 16 − k: **C(16 − k, 5)** ways
   - Total scenarios per discard option: **C(16, k) × C(16 − k, 5)**

| k (discarded) | Draw combos C(16,k) | Opponent combos C(16−k, 5) | Total scenarios |
| ------------- | ------------------- | -------------------------- | --------------- |
| 0             | 1                   | 4,368                      | **4,368**       |
| 1             | 16                  | 3,003                      | **48,048**      |
| 2             | 120                 | 2,002                      | **240,240**     |
| 3             | 560                 | 1,287                      | **720,720**     |
| 4             | 1,820               | 792                        | **1,441,440**   |
| 5             | 4,368               | 462                        | **2,018,016**   |

### Scenarios per hand (all 32 discard options)

```
  1 × 4,368          (k=0)
+ 5 × 48,048         (k=1, five single-card discards)
+ 10 × 240,240       (k=2)
+ 10 × 720,720       (k=3)
+ 5 × 1,441,440      (k=4)
+ 1 × 2,018,016      (k=5)
= 19,079,424 total scenarios per starting hand
```

### Scale for all hands

For all 20,349 possible starting hands: **20,349 × 19,079,424 ≈ 388 billion** scenarios. This is too large for brute-force in pure Python but manageable with optimization (see Computation Strategy below).

## Metrics to Compute

For each starting hand H and each of its 32 discard options D:

### Core Metrics

| Metric                          | Description                                                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Pre-discard Win %**           | Win probability of keeping the original hand (k=0 baseline, from Turn 1 data)                                            |
| **Post-discard Expected Win %** | Expected win probability after discarding D and drawing replacements, averaged over all draw outcomes and opponent hands |
| **Delta (Δ Win %)**             | Post-discard Win % minus Pre-discard Win % (positive = improvement)                                                      |

### Hand Improvement Metrics

| Metric                     | Description                                                                |
| -------------------------- | -------------------------------------------------------------------------- |
| **P(improve)**             | Probability that the new hand has a **better** hand rank than the original |
| **P(same)**                | Probability that the new hand has the **same** hand rank                   |
| **P(worsen)**              | Probability that the new hand has a **worse** hand rank                    |
| **Best possible outcome**  | The highest hand rank achievable from this discard (e.g. "Four of a Kind") |
| **Worst possible outcome** | The lowest hand rank achievable from this discard                          |

### Risk Assessment Metrics

| Metric                  | Description                                                    |
| ----------------------- | -------------------------------------------------------------- |
| **EV (Expected Value)** | The expected win % after discard — higher is better            |
| **Upside**              | Max achievable win % − current win % (how much you COULD gain) |
| **Downside**            | Current win % − min achievable win % (how much you COULD lose) |
| **Risk Ratio**          | Upside / Downside — values > 1 favor taking the risk           |
| **Recommendation**      | "Keep" / "Discard [cards]" based on highest EV                 |

### Risk Decision Example

Suppose you have **Three Jacks + Queen + 10** (Three of a Kind, ~76% win):

| Discard Option          | Expected Win % | Δ Win % | P(improve) | P(worsen) | Risk Ratio | Note                         |
| ----------------------- | -------------- | ------- | ---------- | --------- | ---------- | ---------------------------- |
| Keep all                | 76.0%          | —       | —          | —         | —          | Baseline                     |
| Discard Q, 10           | 78.5%          | +2.5%   | 22%        | 8%        | 2.75       | Good risk: likely to improve |
| Discard 10 only         | 77.2%          | +1.2%   | 15%        | 3%        | 5.00       | Safe: small gain, low risk   |
| Discard Q only          | 76.8%          | +0.8%   | 12%        | 4%        | 3.00       | Marginal                     |
| Discard J (break trips) | 51.0%          | −25.0%  | 3%         | 85%       | 0.04       | Terrible: destroys your hand |

_(Numbers are illustrative, not computed.)_

The optimal play is the discard with the **highest expected win %**, but the risk metrics help you understand the variance — are you gambling on a small chance of a huge upgrade, or making a safe incremental improvement?

## Computation Strategy

### Challenge

~388 billion scenarios across all 20,349 hands is expensive. Integer comparisons are fast, but the sheer volume requires optimization.

### Approach: Precomputed Keys + Exhaustive Enumeration

1. **Precompute all hand keys** — reuse the Turn 1 `score_to_key()` mapping for all C(21,5) = 20,349 possible hands. Store as `dict[frozenset → int]` for O(1) lookup.

2. **For each starting hand** (20,349 iterations):
   - Compute pool = 16 remaining card indices
   - Pre-discard win % = from Turn 1 data (already computed)

3. **For each discard option** (32 per hand):
   - remaining = kept card indices
   - For each draw combo from pool (C(16,k) draws):
     - new_hand = remaining ∪ draw → look up precomputed key
     - reduced_pool = pool − draw (16−k cards)
     - For each opponent combo from reduced_pool (C(16−k, 5)):
       - Look up opponent key
       - Compare: win / loss / tie
   - Aggregate into expected win %, improvement probabilities, etc.

4. **Optimizations:**
   - **Skip symmetric discards**: Hands with identical-rank cards in different suits produce equivalent discard outcomes — prune duplicates.
   - **Early termination**: If k=0 (keep all) has very high win % (e.g. >98%), discarding is almost never optimal — skip detailed computation.
   - **Vectorized comparison**: For a given draw outcome, batch all opponent keys into a sorted array and use binary search to count wins/ties instead of iterating.
   - **Parallel processing**: Each starting hand is independent — use multiprocessing for parallelism.
   - **Never discard Joker**

### Expected Runtime

With optimized Python (precomputed keys, vectorized opponent comparison):

- Can be reduced with multiprocessing or Monte Carlo approximation

## Output Files

### `discard_analysis.csv` — Full Discard Table

One row per (starting hand, discard option) — up to 20,349 × 32 = **651,168 rows**.

| Column              | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| Hand                | Starting 5 cards (e.g. "As Ah Jd Tc W")                    |
| Hand Type           | Original hand category (e.g. "Three of a Kind")            |
| Pre-Discard Win %   | Win % if you keep all cards (baseline)                     |
| Discard             | Cards discarded (e.g. "Tc" or "Jd Tc" or "—" for keep all) |
| Cards Discarded (k) | Number of cards discarded (0–5)                            |
| Post-Discard Win %  | Expected win % after discard and redraw                    |
| Delta %             | Change from baseline (positive = improvement)              |
| P(Improve)          | Probability hand rank improves                             |
| P(Same)             | Probability hand rank stays the same                       |
| P(Worsen)           | Probability hand rank worsens                              |
| Best Outcome        | Best achievable hand type after draw                       |
| Worst Outcome       | Worst achievable hand type after draw                      |
| Risk Ratio          | Upside / Downside ratio                                    |

### `optimal_discard.csv` — Best Strategy Per Hand

One row per starting hand — **20,349 rows**.

| Column            | Description                                  |
| ----------------- | -------------------------------------------- |
| Hand              | Starting 5 cards                             |
| Hand Type         | Original hand category                       |
| Pre-Discard Win % | Baseline win %                               |
| Optimal Discard   | Which cards to discard for highest EV        |
| Optimal Win %     | Expected win % after optimal discard         |
| Delta %           | Improvement over keeping all                 |
| P(Improve)        | Probability of improving hand rank           |
| Risk Ratio        | Upside / Downside                            |
| Verdict           | "Keep" if Δ ≤ 0, otherwise "Discard [cards]" |

### `discard_summary_by_type.csv` — Strategy Summary by Hand Category

One row per hand type — **8 rows**.

| Column                      | Description                                        |
| --------------------------- | -------------------------------------------------- |
| Hand Type                   | e.g. "Three of a Kind"                             |
| Count                       | Number of starting hands of this type              |
| Avg Pre-Discard Win %       | Average baseline win %                             |
| Avg Optimal Win %           | Average win % after optimal discard                |
| Avg Delta %                 | Average improvement                                |
| % Hands Where Discard Helps | Fraction of hands where optimal play is to discard |
| Most Common Optimal k       | Most frequent number of cards discarded            |

## Key Questions This Answers

1. **Should I ever discard from a Three of a Kind?** — Does discarding the 2 kickers for a chance at Four of a Kind produce a higher expected win % than keeping?

2. **How much does the Joker change discard strategy?** — With the Joker, discarding to complete Five of a Kind might be worthwhile even from a strong base hand.

3. **Is discarding from a Pair ever correct?** — Pair hands have low baseline win %. Does aggressive discarding (3 cards) give a meaningful boost?

4. **When is "keep all" optimal?** — For which hand types is the risk of drawing worse cards never worth the potential upgrade?

5. **Are there trap discards?** — Discard options that look appealing (e.g. break Two Pair to chase Three of a Kind) but actually lower expected win %?

## Usage

```bash
python discard_calculator.py
```

The script reads precomputed Turn 1 data (hand keys) and outputs the three CSV files above.

## Notation (same as Turn 1 calculator)

- Suits: `s` (spade), `h` (heart), `d` (diamond), `c` (club)
- Joker: `W`
- 10: `T`
- Example hand: `As Kh Qd Jc W`
- Discard notation: `"Qd Jc"` means discard Queen of diamonds and Jack of clubs
- `"—"` means keep all (no discard)
