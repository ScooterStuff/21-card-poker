# 21 Card Poker — Meta-Game Strategy Summary

## Overview

Beyond pure hand optimization (discard analysis), 21 Card Poker has a rich **information game** layered on top. Both players observe each other's discard count during the draw phase, creating opportunities for **reads**, **deception**, and **Bayesian inference**.

This document catalogs the strategic dimensions available to players.

---

## Strategy 1: Reading the Opponent's Discard Count

When the opponent discards k cards, that number **leaks information** about their hand type. Assuming the opponent plays optimally:

| Opponent k | Likely Hand Types                                                                                                  | Reasoning                                                                     |
| :--------: | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
|     0      | Five of a Kind, Royal Flush, Straight, Four of a Kind (strong), Full House                                         | Hand is already strong — no card swap improves expected value                 |
|     1      | Four of a Kind (upgrading kicker), Two Pair (chasing Full House), strong Three of a Kind (swapping weakest kicker) | Keeping 4 solid cards, replacing the weakest                                  |
|     2      | Three of a Kind (replacing 2 kickers for Full House / Four of a Kind chance), Pair with one decent kicker          | The most common "standard" draw                                               |
|     3      | Pair (keeping the pair, replacing 3 unrelated cards)                                                               | Weak hand hoping to improve                                                   |
|     4      | Keeping only the Joker (or a single strong card)                                                                   | Very weak starting hand                                                       |
|     5      | Essentially nothing worth keeping                                                                                  | Extremely rare — pigeonhole principle guarantees at least a Pair in this deck |

### Why This Matters

If the opponent discards 0, you can be fairly confident they hold a strong hand. This should factor into your **post-draw betting decision** — calling a big bet against a k=0 opponent is riskier than against a k=3 opponent.

### Caveat

These are the "honest" (GTO-optimal) mappings. A deceptive player may deliberately use a non-optimal k to mislead (see Strategy 4).

---

## Strategy 2: Information Advantage from Drawing More Cards

Every card you draw is a card you **know the opponent doesn't have**. Drawing more cards reduces uncertainty about the opponent's hand.

| Your k | Cards you see (your hand) | Unknown cards for opponent's hand | Your information advantage           |
| :----: | :-----------------------: | :-------------------------------: | ------------------------------------ |
|   0    |       5 (original)        |         16 possibilities          | Minimal — you only know your 5 cards |
|   1    |   5 (4 kept + 1 drawn)    |         15 possibilities          | Slightly better                      |
|   2    |   5 (3 kept + 2 drawn)    |         14 possibilities          | Moderate                             |
|   3    |   5 (2 kept + 3 drawn)    |         13 possibilities          | Good                                 |
|   4    |   5 (1 kept + 4 drawn)    |         12 possibilities          | Strong                               |
|   5    |        5 (all new)        |         11 possibilities          | Maximum                              |

Additionally, your **discarded cards** are removed from play. You know the opponent can't have them either (they were in your hand, not in the deal pool). So after discarding k cards and drawing k replacements, you have knowledge of **5 + k specific cards** that the opponent does NOT hold:

- 5 cards currently in your hand
- k cards you discarded (removed from play)

This means the opponent's 5 cards must come from a pool of **21 − 5 − k = 16 − k** cards.

### Strategic Implication

There is a secondary benefit to discarding beyond hand improvement: **information**. Even if discarding 3 cards only marginally improves your hand, knowing 8 cards (5 in hand + 3 discarded) that the opponent doesn't have gives you a much better read for post-draw betting.

---

## Strategy 3: Post-Draw Bayesian Inference

After the draw phase, you know:

1. Your own 5 cards
2. Your k discarded cards (dead cards)
3. The opponent's discard count (k_opp)

From this, you can compute a **posterior probability distribution** over the opponent's hand.

### Example Inference

> You hold: A♠ A♥ A♦ K♣ K♥ (Full House, Aces over Kings)
> You discarded 0 cards.
> Opponent discarded 2 cards.

Since opponent discarded 2, they likely started with Three of a Kind or a Pair (from the read table). Their post-draw hand is built from:

- 3 kept cards + 2 newly drawn cards
- Drawn from the 11-card draw pile (which you don't fully know)
- But you DO know A♠, A♥, A♦, K♣, K♥ are NOT in their hand

You can enumerate all possible opponent hands consistent with these constraints and compute:

- P(opponent beats you)
- P(opponent ties you)
- P(you beat opponent)

This informs whether to check, bet, or fold in post-draw betting.

---

## Strategy 4: Deceptive Discarding (Bluffing with k)

If you always discard the optimal k, **your discard count becomes a reliable signal** that a smart opponent exploits:

| Your optimal k | What opponent infers     | How they exploit it                               |
| -------------- | ------------------------ | ------------------------------------------------- |
| k=0            | You have a monster hand  | They fold to your bets → you win small pots       |
| k=2            | You have Three of a Kind | They know your approximate strength               |
| k=3            | You have a weak Pair     | They raise aggressively → you face hard decisions |

### Counter-Strategy: Deceptive k

Sometimes it's worth making a **suboptimal discard** to disguise your hand strength:

- **With Three of a Kind (optimal k=2)**: Discard 0 (keep all) → opponent reads you as Royal Flush / Four of a Kind → they fold more to your post-draw bets
- **With Four of a Kind (optimal k=1 or k=0)**: Discard 2 → opponent reads you as Three of a Kind → they call your bets more → you win bigger pots
- **With a Pair (optimal k=3)**: Discard 1 → opponent reads you as Four of a Kind → they may fold a hand that would have beaten you

### The Key Trade-off

Every deceptive discard has a **cost** (lower expected hand strength) and a **benefit** (misleading the opponent in post-draw betting). The question:

> _"Is the information warfare value of disguising my k worth the X% decrease in expected hand quality?"_

If the EV cost is small (e.g., switching from k=2 to k=0 only costs 0.5% win rate) but the deception is large (opponent's read shifts dramatically), it's a profitable bluff.

---

## Strategy 5: Reverse Reads (What Your k Tells the Opponent)

Everything you observe about the opponent, **they observe about you**. Your discard count is a two-way signal:

```
Your discard decision
  ├─ Optimizes your hand (pure math)
  └─ Sends a signal to opponent (game theory)
```

An unexploitable (GTO) strategy would **randomize** discard choices in certain spots to prevent the opponent from gaining reliable reads. For example, with Three of a Kind:

- 70% of the time: discard 2 (optimal)
- 20% of the time: discard 0 (disguised as monster)
- 10% of the time: discard 1 (disguised as Four of a Kind / Two Pair)

The exact mixing frequencies depend on the EV cost of each alternative and the betting structure.

---

## Strategy 6: Turn Order Exploitation (Follower vs. Starter)

In the draw phase:

1. **Follower (F) discards first**
2. Starter (S) sees F's discard count, then discards

This means:

- **Starter has strictly more information** — they see F's k before deciding their own k
- S can adjust their discard and post-draw betting strategy based on F's k

### Follower's Dilemma

F knows that S will observe their k. This creates additional pressure on F to consider deception — because the information cost of an honest k is higher when the observer acts after you.

### Starter's Advantage

S can build a **conditional strategy**:

| F discards | S's adjustment                                                         |
| ---------- | ---------------------------------------------------------------------- |
| 0          | F is likely strong → S should be cautious unless S is also very strong |
| 1          | F has Four of a Kind or Two Pair → S knows the landscape               |
| 3+         | F is likely weak → S can play aggressively in post-draw betting        |

---

## Strategy 7: Chip Stack Dynamics

Discard strategy should also account for the **current chip situation**:

- **When ahead in chips**: Play conservatively — keep strong hands (k=0), avoid risky draws. You can grind out a win with safe post-draw betting.
- **When behind in chips**: Take bigger gambles — the EV of a risky draw (k=3, k=4) increases when you need to catch up. The "cost of deception" matters less when you're desperate.
- **Near elimination**: All-in dynamics change discard math entirely — post-draw betting is moot if both players will be all-in regardless.

---

## Strategy Summary Table

| Strategy              | Source of Value                                      | Exploited By                                | Counter                         |
| --------------------- | ---------------------------------------------------- | ------------------------------------------- | ------------------------------- |
| Read opponent's k     | Information leak from discard count                  | Naive opponents who always play optimally   | Deceptive discarding            |
| Draw more = know more | Seeing drawn cards eliminates opponent possibilities | — (always beneficial, no counter)           | —                               |
| Bayesian inference    | Combining your cards + opponent k + game constraints | Opponents who bet predictably               | Unpredictable post-draw betting |
| Deceptive k           | Misleading the opponent's read                       | Opponents who rely on k-to-hand-type tables | Mixed strategies, varying reads |
| Reverse reads         | Opponent reads YOUR k                                | You, if you're always predictable           | Mixing/randomization            |
| Turn order            | Starter sees Follower's k                            | Follower (information disadvantage)         | Follower deception / aggression |
| Chip dynamics         | Adjusting risk based on game state                   | Risk-averse players when behind             | Context-aware strategy          |

---

## What Can Be Computed vs. What Requires Judgment

| Aspect                                                          | Computable?  | Method                                            |
| --------------------------------------------------------------- | ------------ | ------------------------------------------------- |
| Optimal discard for max hand EV                                 | ✅ Yes       | discard_calculator.py (already done)              |
| P(hand type \| opponent k)                                      | ✅ Yes       | Count from optimal discard data                   |
| Posterior opponent hand distribution given your cards + their k | ✅ Yes       | Combinatorial enumeration                         |
| Information gain from each k choice                             | ✅ Yes       | Entropy reduction calculation                     |
| Cost of deceptive discard (EV difference)                       | ✅ Yes       | Compare optimal vs. alternative k                 |
| Optimal mixing frequencies for deception                        | ⚠️ Partially | Requires game-theoretic solver (Nash equilibrium) |
| Full GTO strategy with bluffing                                 | ❌ Complex   | Would need full game tree search                  |

The **statistical exploration** document details how to compute all the ✅ items.
