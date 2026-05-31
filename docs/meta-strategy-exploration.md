# 21 Card Poker — Meta-Strategy Statistical Exploration

## Objective

Using the precomputed optimal discard data (from `discard_calculator.py`), compute the **information and deception layer** of the game — how discard counts reveal hand types, how much information each draw provides, and how much it costs to bluff with a non-optimal discard.

This answers questions like:

- _"If my opponent discards 2, what's the probability they have Three of a Kind?"_
- _"How much win% do I sacrifice by discarding 0 instead of 2, to disguise my Three of a Kind?"_
- _"After I draw and see specific cards, what's the probability distribution over opponent hands?"_

## Prerequisites

This analysis reads from the output of `discard_calculator.py`:

- `optimal_discard.csv` — best strategy per hand (which k each hand would optimally choose)
- `discard_analysis.csv` — all 32 discard options per hand with expected win %

It also reuses the precomputed hand evaluations from Phase 1 of `discard_calculator.py`.

---

## Part A: Opponent Read Table — P(Hand Type | Opponent Discards k)

### What We're Computing

For each possible discard count k ∈ {0, 1, 2, 3, 4, 5}, compute the probability distribution over opponent hand types, assuming the opponent **plays optimally** (always chooses the k that maximizes expected win %).

### Method

1. Load `optimal_discard.csv` — each row tells us: starting hand → optimal k.
2. Group all 20,349 hands by their **optimal k**.
3. For each group, count how many hands fall into each hand type (Pair, Two Pair, Three of a Kind, etc.).
4. Normalize to get **P(Hand Type | k)**.

### Output: `read_table.csv`

| Opponent k | Hand Type      | Count | P(Hand Type \| k) | Avg Pre-Discard Win % | Avg Post-Discard Win % |
| ---------- | -------------- | ----- | ----------------- | --------------------- | ---------------------- |
| 0          | Five of a Kind | 5     | X%                | 100.00%               | 100.00%                |
| 0          | Royal Flush    | 24    | X%                | 99.87%                | 99.87%                 |
| 0          | Four of a Kind | ...   | ...               | ...                   | ...                    |
| 1          | Four of a Kind | ...   | ...               | ...                   | ...                    |
| ...        | ...            | ...   | ...               | ...                   | ...                    |

### Additional Derived Metrics

For each k, compute:

| Metric                        | Description                                                      |
| ----------------------------- | ---------------------------------------------------------------- |
| **P(strong \| k)**            | P(opponent hand type ≤ Straight), i.e. hand rank 1–5             |
| **P(weak \| k)**              | P(opponent hand type ≥ Three of a Kind), i.e. hand rank 6–8      |
| **E[opponent win % \| k]**    | Expected opponent post-discard win % given they discarded k      |
| **Entropy of hand type \| k** | How uncertain you still are about their hand type after seeing k |

### Scale

20,349 hands × 1 lookup each = trivial (< 1 second).

---

## Part B: Information Advantage Quantification

### What We're Computing

For each starting hand and each discard count k, measure how much **information** you gain about the opponent's hand by drawing k cards.

### Information Gain Mechanics

After you discard k cards and draw k replacements:

| What you know              | Count | Effect                                                             |
| -------------------------- | ----- | ------------------------------------------------------------------ |
| Your 5 current cards       | 5     | Opponent cannot have these                                         |
| Your k discarded cards     | k     | Removed from play — opponent cannot have these                     |
| **Total known exclusions** | 5 + k | Opponent's 5 cards come from 21 − 5 − k = **16 − k** possibilities |

| Your k | Opponent pool size | Possible opponent hands C(16−k, 5) | Reduction from k=0 |
| ------ | ------------------ | ---------------------------------- | ------------------ |
| 0      | 16                 | 4,368                              | baseline           |
| 1      | 15                 | 3,003                              | −31.2%             |
| 2      | 14                 | 2,002                              | −54.2%             |
| 3      | 13                 | 1,287                              | −70.5%             |
| 4      | 12                 | 792                                | −81.9%             |
| 5      | 11                 | 462                                | −89.4%             |

### Method

For each starting hand and discard count k:

1. Compute the opponent pool (16 − k remaining cards).
2. Enumerate all C(16 − k, 5) possible opponent hands.
3. Compute the **distribution of opponent hand types** in this pool.
4. Compute **entropy** of this distribution: H = −Σ p(type) × log₂(p(type)).
5. Compare entropy at k vs. k=0 → **information gain** = H(k=0) − H(k).

### Beyond Card Counting: Combining with Draw Outcome

When you draw specific cards, you gain **even more** information. For each specific draw outcome:

1. Your new hand is known → your own strength is fixed.
2. Opponent's pool is the specific 16 − k cards you DIDN'T draw.
3. Enumerate opponent hands from that specific pool → compute exact P(you win | your draw, opponent plays from this pool).

This gives a **per-draw** confidence level — some draws leave you very certain about the matchup, others leave it ambiguous.

### Metric: Information-Adjusted EV

For each discard option, compute:

| Metric               | Description                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Raw EV**           | Expected win % (pure hand optimization — from discard_calculator.py)                                         |
| **Info Gain (bits)** | Entropy reduction about opponent's hand type                                                                 |
| **Certainty %**      | Fraction of draw outcomes where your win probability is > 80% or < 20% (you KNOW whether you'll win or lose) |
| **Ambiguity %**      | Fraction of draw outcomes where win probability is 40%–60% (coin flip — no clear read)                       |

### Output: `information_advantage.csv`

One row per (starting hand, discard option):

| Column             | Description                                         |
| ------------------ | --------------------------------------------------- |
| Hand               | Starting 5 cards                                    |
| Hand Type          | Original hand category                              |
| k                  | Cards discarded                                     |
| Raw EV (Win %)     | Expected win % from pure hand optimization          |
| Opponent Pool Size | 16 − k                                              |
| Opponent Hands     | C(16−k, 5)                                          |
| Entropy (bits)     | Uncertainty about opponent hand type after draw     |
| Info Gain vs k=0   | H(k=0) − H(k)                                       |
| Certainty %        | % of draw outcomes where win prob is > 80% or < 20% |
| Ambiguity %        | % of draw outcomes where win prob is 40%–60%        |

### Scale

For each hand × discard option × draw combo, we're doing the opponent enumeration we already did in `discard_calculator.py`. We can extract the per-draw statistics from the same computation — it's an extension of the existing inner loop.

For the entropy calculation over all hands: 20,349 hands × ~6 k-values × C(16−k, 5) opponent enumerations. The entropy part itself is lightweight.

---

## Part C: Deception Cost Analysis

### What We're Computing

For each starting hand, measure the **cost of bluffing** — how much expected win % you sacrifice by choosing a non-optimal discard count to mislead the opponent.

### Method

From `discard_analysis.csv`, for each starting hand we already have the expected win % for every discard option. We extract:

1. **Optimal k** and its win % (from `optimal_discard.csv`).
2. **Best alternative for each k** — the highest-EV discard option that uses exactly k cards. For example, if optimal is k=2, what's the best k=0 option? The best k=1 option?
3. **Deception cost** = Optimal win % − Alternative win %.
4. **Signal shift** = How different the opponent's read would be.

### Deception Cost Table

For each hand type, compute the average cost of mimicking a different k:

| Your Hand Type  | Optimal k | Mimic k=0 Cost | Mimic k=1 Cost | Mimic k=2 Cost | Mimic k=3 Cost |
| --------------- | --------- | -------------- | -------------- | -------------- | -------------- |
| Three of a Kind | 2         | −X%            | −Y%            | (optimal)      | −Z%            |
| Pair            | 3         | −X%            | −Y%            | −Z%            | (optimal)      |
| Four of a Kind  | 0 or 1    | (optimal)      | ...            | −Y%            | −Z%            |
| ...             | ...       | ...            | ...            | ...            | ...            |

### "Cheap Bluffs" — High-Value Deception Spots

A **cheap bluff** is a discard choice where:

- The deception cost is **small** (< 1–2% win rate)
- The signal shift is **large** (opponent's read changes dramatically)

For example: Three of a Kind where k=0 gives 75.8% win and k=2 (optimal) gives 76.3% win → the 0.5% cost is small, but the opponent reads "k=0" as a monster hand.

### Output: `deception_cost.csv`

One row per (starting hand, alternative k):

| Column              | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| Hand                | Starting 5 cards                                           |
| Hand Type           | Original hand category                                     |
| Optimal k           | Best discard count for hand EV                             |
| Optimal Win %       | Win % at optimal k                                         |
| Alternative k       | The non-optimal k being considered                         |
| Alternative Win %   | Best win % achievable at this k                            |
| Deception Cost (Δ%) | Optimal − Alternative (positive = sacrifice)               |
| Opponent Read Shift | What hand types the opponent would assume at alternative k |

### Output: `deception_summary.csv`

Aggregated by hand type:

| Column                  | Description                                                  |
| ----------------------- | ------------------------------------------------------------ |
| Hand Type               | e.g. "Three of a Kind"                                       |
| Count                   | Number of hands of this type                                 |
| Optimal k (mode)        | Most common optimal k                                        |
| Avg Cost to Mimic k=0   | Average win % lost by keeping all                            |
| Avg Cost to Mimic k=1   | Average win % lost by discarding 1                           |
| ...                     | ...                                                          |
| Cheapest Bluff k        | The k with lowest average deception cost (excluding optimal) |
| Avg Cheapest Bluff Cost | Average sacrifice for the cheapest bluff                     |
| % Hands with Bluff < 1% | Fraction of hands where the cheapest bluff costs < 1%        |

---

## Part D: Conditional Post-Draw Opponent Model

### What We're Computing

After the draw phase is complete and you enter post-draw betting, you know:

1. Your own 5 cards (known)
2. Your discarded cards (known, dead)
3. Opponent's discard count k_opp (observed)

Given this, compute the **posterior probability distribution** over opponent hand types and your **conditional win probability**.

### Method

1. Your known dead cards: 5 (in hand) + k_yours (discarded) = 5 + k_yours cards.
2. Remaining cards in play: 21 − 5 − k_yours = 16 − k_yours.
3. Of these, opponent holds 5 and the rest are unused in the draw pile.
4. Enumerate all C(16 − k_yours, 5) possible opponent hands.
5. **Filter by opponent k:** The opponent discarded k_opp cards and drew k_opp replacements, but we don't know WHICH cards they discarded or drew. However, the resulting opponent hand is a 5-card hand from the 16 − k_yours remaining cards. Since we don't know the opponent's discard/draw process in detail, we model their final hand as any 5-card combination from the remaining pool.
6. For each possible opponent hand, look up its key and compare against your hand's key.

### Bayesian Update Using Opponent k

The raw enumeration in step 4–6 treats all opponent hands as equally likely. But we know the opponent discarded k_opp cards, which makes certain hand types more or less likely (from Part A's read table).

To incorporate this:

1. From Part A, we have **P(hand type | k_opp)** — the prior probability of each hand type given opponent's discard count.
2. For each possible opponent hand (from the enumeration), assign a **weight** proportional to P(hand type | k_opp) for that hand's type.
3. Compute **weighted win probability** using these Bayesian weights.

### Output: `post_draw_model.csv`

One row per (your hand, opponent k_opp):

| Column                   | Description                                      |
| ------------------------ | ------------------------------------------------ |
| Your Hand                | Your post-draw 5 cards                           |
| Your Hand Type           | Your hand category                               |
| Your k                   | How many you discarded                           |
| Opponent k               | How many they discarded                          |
| Naive Win %              | Win % assuming all opponent hands equally likely |
| Bayesian Win %           | Win % weighted by P(hand type \| opponent k)     |
| Δ (Bayes − Naive)        | How much the read changes your assessment        |
| P(Opp has stronger hand) | Weighted probability opponent beats you          |
| Most Likely Opp Type     | Hand type with highest posterior probability     |

### Scale

This analysis is per post-draw hand (20,349 possible) × 6 opponent k values = ~122K rows. Each row requires enumerating C(16−k, 5) opponent hands — same complexity as the baseline calculation in probability_calculator.py. Feasible in minutes.

---

## Computation Strategy

### Architecture

```
meta_strategy_calculator.py
  ├── Phase 1: Load precomputed data
  │     ├── optimal_discard.csv (read)
  │     ├── discard_analysis.csv (read)
  │     └── Recompute hand evaluation lookup (same as discard_calculator Phase 1)
  │
  ├── Phase 2 (Part A): Read Table computation — trivial, < 1 second
  │     └── Output: read_table.csv
  │
  ├── Phase 3 (Part C): Deception Cost — lightweight, reads from discard_analysis.csv
  │     └── Output: deception_cost.csv, deception_summary.csv
  │
  ├── Phase 4 (Part B): Information Advantage — moderate, reuses discard inner loop
  │     └── Output: information_advantage.csv
  │
  └── Phase 5 (Part D): Post-Draw Opponent Model — moderate, per-hand enumeration
        └── Output: post_draw_model.csv
```

### Data Dependencies

```
discard_calculator.py outputs
  │
  ├── optimal_discard.csv ──→ Part A (read table)
  │                       ──→ Part C (deception cost baseline)
  │
  ├── discard_analysis.csv ──→ Part C (all k alternatives)
  │                        ──→ Part B (per-k win% data)
  │
  └── hand evaluation arrays ──→ Part B (entropy calc)
                              ──→ Part D (opponent enumeration)
```

### Estimated Complexity

| Part                         | Computation                                      | Estimated Time                                      |
| ---------------------------- | ------------------------------------------------ | --------------------------------------------------- |
| A — Read Table               | 20,349 lookups                                   | < 1 second                                          |
| C — Deception Cost           | Aggregation over ~573K rows from CSV             | < 10 seconds                                        |
| B — Information Advantage    | Per-hand entropy + certainty metrics             | Minutes (similar to probability_calculator)         |
| D — Post-Draw Opponent Model | 20,349 hands × 6 k-values × opponent enumeration | Minutes–hours depending on Bayesian weighting depth |

Parts A and C are fast (pure aggregation). Parts B and D involve combinatorial enumeration but are parallelizable (same pattern as `discard_calculator.py`).

---

## Output Files Summary

| File                        | Rows                                 | Description                                      |
| --------------------------- | ------------------------------------ | ------------------------------------------------ |
| `read_table.csv`            | ~48 (8 types × 6 k-values)           | P(Hand Type \| opponent k)                       |
| `information_advantage.csv` | ~573K (all hand × discard options)   | Entropy and certainty metrics per discard choice |
| `deception_cost.csv`        | ~102K (hands × alternative k-values) | Cost of each non-optimal k                       |
| `deception_summary.csv`     | ~48 (8 types × 6 k-values)           | Average bluff cost by hand type                  |
| `post_draw_model.csv`       | ~122K (hands × 6 opponent k-values)  | Bayesian post-draw win probability               |

---

## Key Questions This Answers

1. **If my opponent discards 2 cards, what hand do they likely have?** → Part A read table gives P(Three of a Kind | k=2) etc.

2. **How much information do I gain by discarding 3 instead of 1?** → Part B information advantage shows entropy reduction.

3. **Can I disguise my Three of a Kind as a monster hand by keeping all cards? What does it cost?** → Part C deception cost gives the exact win % sacrifice.

4. **Are there hands where bluffing is essentially free?** → Part C "cheap bluffs" filter (cost < 1%) identifies them.

5. **After the draw, given I see my cards and know opponent discarded k, what's my actual win probability?** → Part D post-draw model gives Bayesian-adjusted win %.

6. **Is it ever worth discarding suboptimally for information gain + deception, when you combine all factors?** → Comparing Part B (info value) + Part C (deception value) against Raw EV loss.

---

## Usage

```bash
# Prerequisite: discard_calculator.py must have been run first
python meta_strategy_calculator.py
```

The script reads the precomputed discard analysis CSV files and the 21-card deck evaluations, then outputs the five analysis CSV files above.
