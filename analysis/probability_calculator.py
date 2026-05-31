"""
21 Card Poker — Pre-Discard Win Probability Calculator

Enumerates ALL possible 5-card starting hands from the 21-card deck
and computes each hand's win/loss/tie probability against all possible
opponent hands (pre-draw, no discard).

Output:
  hand_probabilities.csv      — Full table (20,349 rows)
  hand_type_summary.csv       — Aggregated by hand category

Usage:
  python probability_calculator.py
"""

import itertools
import csv
import time
from collections import defaultdict

from core.game_logic import Card, JOKER, RANKS, SUITS
from core.hand_eval import evaluate_player_hand, compare_scores


# ── Helpers ───────────────────────────────────────────────────────

def build_deck() -> list[Card]:
    """Build the ordered 21-card deck (deterministic ordering for indexing)."""
    cards = []
    for r in RANKS:
        for s in SUITS:
            cards.append(Card(rank=r, suit=s))
    cards.append(JOKER)
    return cards


def score_to_key(score: tuple) -> int:
    """Convert a hand-evaluation score tuple into a single integer
    where **higher = better hand**. This allows fast integer comparison
    instead of calling compare_scores() in the inner loop.

    Encoding: base-6 positional system with inverted hand rank.
      key = (9 - hand_rank) * 6^4  +  tb1 * 6^3  +  tb2 * 6^2  +  tb3 * 6  +  tb4
    Tiebreaker values are 0-5 (rank values: 10→1, J→2, Q→3, K→4, A→5).
    """
    key = 9 - score[0]  # Invert: rank 1 (best) → 8, rank 8 (worst) → 1
    for i in range(1, 5):
        val = score[i] if i < len(score) else 0
        key = key * 6 + val
    return key


def hand_to_str(cards: list[Card]) -> str:
    """Format hand for CSV: use s/h/d/c for suits, W for Joker, T for 10."""
    parts = []
    for c in cards:
        if c.is_joker:
            parts.append("W")
        else:
            rank = "T" if c.rank == "10" else c.rank
            suit_map = {"♠": "s", "♥": "h", "♦": "d", "♣": "c"}
            suit = suit_map.get(c.suit, c.suit)
            parts.append(f"{rank}{suit}")
    return " ".join(parts)


# ── Main ──────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  21 Card Poker — Pre-Discard Win Probability Calculator")
    print("=" * 65)

    deck = build_deck()
    n = len(deck)  # 21
    assert n == 21, f"Deck has {n} cards, expected 21"

    # ── Phase 1: Enumerate & evaluate all hands ───────────────────

    print(f"\nDeck: {n} cards")
    all_hands = list(itertools.combinations(range(n), 5))
    total_hands = len(all_hands)
    print(f"Possible 5-card hands: C({n},5) = {total_hands:,}")

    print("\nPhase 1 — Evaluating all hands …")
    t0 = time.time()

    hand_key: dict[tuple, int] = {}       # combo → comparable int key
    hand_name: dict[tuple, str] = {}      # combo → hand type name
    hand_cards: dict[tuple, list] = {}    # combo → Card objects

    for combo in all_hands:
        cards = [deck[i] for i in combo]
        score, name, _joker = evaluate_player_hand(cards)
        hand_key[combo] = score_to_key(score)
        hand_name[combo] = name
        hand_cards[combo] = cards

    t1 = time.time()
    print(f"  ✓ {total_hands:,} hands evaluated in {t1 - t0:.1f}s")

    # ── Phase 2: Compute win probabilities ────────────────────────

    opponent_count = 4368  # C(16,5)
    total_comparisons = total_hands * opponent_count
    print(f"\nPhase 2 — Computing win probabilities …")
    print(f"  Each hand vs C(16,5) = {opponent_count:,} opponent hands")
    print(f"  Total comparisons: {total_comparisons:,}")

    t2 = time.time()
    results = []

    for idx, h1 in enumerate(all_hands):
        if idx % 2000 == 0:
            elapsed = time.time() - t2
            pct = idx / total_hands * 100
            rate = idx / max(elapsed, 0.001)
            eta = (total_hands - idx) / max(rate, 1)
            print(f"  [{pct:5.1f}%]  hand {idx:>6,}/{total_hands:,}"
                  f"   elapsed {elapsed:>5.0f}s   ETA {eta:>5.0f}s")

        k1 = hand_key[h1]
        h1_set = set(h1)
        remaining = [i for i in range(n) if i not in h1_set]

        wins = 0
        losses = 0
        ties = 0

        for h2 in itertools.combinations(remaining, 5):
            k2 = hand_key[h2]
            if k1 > k2:
                wins += 1
            elif k1 < k2:
                losses += 1
            else:
                ties += 1

        total = wins + losses + ties  # always 4368
        cards = hand_cards[h1]

        results.append({
            "hand": hand_to_str(cards),
            "type": hand_name[h1],
            "win_pct": wins / total * 100,
            "loss_pct": losses / total * 100,
            "tie_pct": ties / total * 100,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "total": total,
            "has_joker": any(deck[i].is_joker for i in h1),
        })

    t3 = time.time()
    print(f"\n  ✓ Done in {t3 - t2:.1f}s  ({total_comparisons / (t3 - t2):,.0f} cmp/s)")

    # Sort by win % descending (ties broken by loss % ascending)
    results.sort(key=lambda r: (r["win_pct"], -r["loss_pct"]), reverse=True)

    # ── Phase 3: Write full CSV ───────────────────────────────────

    csv_full = "data/hand_probabilities.csv"
    print(f"\nPhase 3 — Writing {csv_full} …")

    with open(csv_full, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Rank", "Hand", "Hand Type", "Has Joker",
            "Win %", "Loss %", "Tie %",
            "Wins", "Losses", "Ties", "Total Matchups",
        ])
        for i, r in enumerate(results, 1):
            writer.writerow([
                i,
                r["hand"],
                r["type"],
                "Yes" if r["has_joker"] else "No",
                f'{r["win_pct"]:.2f}',
                f'{r["loss_pct"]:.2f}',
                f'{r["tie_pct"]:.2f}',
                r["wins"],
                r["losses"],
                r["ties"],
                r["total"],
            ])

    print(f"  ✓ Wrote {len(results):,} rows to {csv_full}")

    # ── Phase 4: Summary by hand type ─────────────────────────────

    type_data: dict[str, list] = defaultdict(list)
    for r in results:
        type_data[r["type"]].append(r)

    summary = []
    for hand_type, entries in type_data.items():
        wins_list = [e["win_pct"] for e in entries]
        summary.append({
            "type": hand_type,
            "count": len(entries),
            "avg_win": sum(wins_list) / len(wins_list),
            "min_win": min(wins_list),
            "max_win": max(wins_list),
            "avg_loss": sum(e["loss_pct"] for e in entries) / len(entries),
            "avg_tie": sum(e["tie_pct"] for e in entries) / len(entries),
            "joker_count": sum(1 for e in entries if e["has_joker"]),
        })

    summary.sort(key=lambda s: s["avg_win"], reverse=True)

    csv_summary = "data/hand_type_summary.csv"
    with open(csv_summary, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hand Type", "Count", "With Joker", "Avg Win %",
            "Min Win %", "Max Win %", "Avg Loss %", "Avg Tie %",
        ])
        for s in summary:
            writer.writerow([
                s["type"], s["count"], s["joker_count"],
                f'{s["avg_win"]:.2f}', f'{s["min_win"]:.2f}',
                f'{s["max_win"]:.2f}', f'{s["avg_loss"]:.2f}',
                f'{s["avg_tie"]:.2f}',
            ])

    print(f"  ✓ Wrote {len(summary)} rows to {csv_summary}")

    # ── Console summary ───────────────────────────────────────────

    print("\n" + "=" * 85)
    print("  SUMMARY BY HAND TYPE")
    print("=" * 85)
    header = (f"  {'Hand Type':<20} {'Count':>6} {'Joker':>6}"
              f" {'Avg Win%':>9} {'Min Win%':>9} {'Max Win%':>9}"
              f" {'Avg Loss%':>10} {'Avg Tie%':>9}")
    print(header)
    print("  " + "-" * 81)
    for s in summary:
        print(f"  {s['type']:<20} {s['count']:>6} {s['joker_count']:>6}"
              f" {s['avg_win']:>8.2f}% {s['min_win']:>8.2f}% {s['max_win']:>8.2f}%"
              f" {s['avg_loss']:>9.2f}% {s['avg_tie']:>8.2f}%")

    # Top 10 and bottom 10 hands
    print("\n" + "=" * 85)
    print("  TOP 15 STARTING HANDS")
    print("=" * 85)
    print(f"  {'#':>4}  {'Hand':<35} {'Type':<20} {'Win%':>7} {'Loss%':>7} {'Tie%':>7}")
    print("  " + "-" * 81)
    for i, r in enumerate(results[:15], 1):
        print(f"  {i:>4}  {r['hand']:<35} {r['type']:<20}"
              f" {r['win_pct']:>6.2f}% {r['loss_pct']:>6.2f}% {r['tie_pct']:>6.2f}%")

    print("\n" + "=" * 85)
    print("  BOTTOM 15 STARTING HANDS")
    print("=" * 85)
    print(f"  {'#':>4}  {'Hand':<35} {'Type':<20} {'Win%':>7} {'Loss%':>7} {'Tie%':>7}")
    print("  " + "-" * 81)
    for r in results[-15:]:
        idx = results.index(r) + 1
        print(f"  {idx:>4}  {r['hand']:<35} {r['type']:<20}"
              f" {r['win_pct']:>6.2f}% {r['loss_pct']:>6.2f}% {r['tie_pct']:>6.2f}%")

    # Joker vs non-Joker aggregate
    joker_hands = [r for r in results if r["has_joker"]]
    no_joker = [r for r in results if not r["has_joker"]]
    if joker_hands and no_joker:
        avg_j = sum(r["win_pct"] for r in joker_hands) / len(joker_hands)
        avg_nj = sum(r["win_pct"] for r in no_joker) / len(no_joker)
        print(f"\n  Joker Advantage:")
        print(f"    Hands with Joker:    {len(joker_hands):>6,}   avg win = {avg_j:.2f}%")
        print(f"    Hands without Joker: {len(no_joker):>6,}   avg win = {avg_nj:.2f}%")
        print(f"    Joker boost: +{avg_j - avg_nj:.2f} percentage points")

    total_time = time.time() - t0
    print(f"\n  Total time: {total_time:.1f}s")
    print(f"\n  Output files:")
    print(f"    {csv_full:<30} — All {len(results):,} hands with probabilities")
    print(f"    {csv_summary:<30} — Summary by hand type")
    print()


if __name__ == "__main__":
    main()
