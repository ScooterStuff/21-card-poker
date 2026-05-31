"""
21 Card Poker — Draw Phase (Turn 2) Optimal Discard Calculator

For every possible 5-card starting hand from the 21-card deck,
evaluates all discard strategies and finds the optimal discard to
maximize expected win probability at showdown.

Output:
  discard_analysis.csv         — All hands × all discard options
  optimal_discard.csv          — Best strategy per hand (20,349 rows)
  discard_summary_by_type.csv  — Summary by hand category (8 rows)

Usage:
  python discard_calculator.py
"""

import itertools
import csv
import time
from collections import Counter, defaultdict
from multiprocessing import Pool, cpu_count

from core.game_logic import JOKER
from core.hand_eval import evaluate_player_hand, HAND_NAMES
from .probability_calculator import build_deck, score_to_key, hand_to_str


# ── Worker shared state (set by initializer, avoids re-pickling) ──

_key_arr = None    # list[int]: bitmask → comparison key (higher = better)
_rank_arr = None   # list[int]: bitmask → hand rank category (1–8, lower = better)
_joker_idx = None  # int: deck index of the Joker


def _init_worker(key_arr, rank_arr, joker_idx):
    """Initialize each worker process with precomputed lookup arrays."""
    global _key_arr, _rank_arr, _joker_idx
    _key_arr = key_arr
    _rank_arr = rank_arr
    _joker_idx = joker_idx


def _analyze_hand(h1):
    """Analyze all discard options for one starting hand.

    Args:
        h1: tuple of 5 sorted card indices

    Returns:
        (h1, baseline_win_pct, results_list)
        Each result: (discard_indices, k, wins, losses, ties, total,
                      win_pct, p_improve, p_same, p_worsen,
                      best_rank, worst_rank, best_draw_wpct, worst_draw_wpct)
    """
    ka = _key_arr
    ra = _rank_arr
    ji = _joker_idx

    # Hand bitmask and evaluation
    hm = (1 << h1[0]) | (1 << h1[1]) | (1 << h1[2]) | (1 << h1[3]) | (1 << h1[4])
    h1_key = ka[hm]
    h1_rank = ra[hm]

    # Pool: 16 remaining cards
    pool = [i for i in range(21) if not (hm & (1 << i))]

    # ── Baseline (k=0): keep all ──────────────────────────────────
    w = l = t = 0
    for a, b, c, d, e in itertools.combinations(pool, 5):
        ok = ka[(1 << a) | (1 << b) | (1 << c) | (1 << d) | (1 << e)]
        if h1_key > ok:
            w += 1
        elif h1_key < ok:
            l += 1
        else:
            t += 1
    baseline_total = w + l + t
    baseline_wpct = w / baseline_total * 100

    results = []

    # k=0 result
    results.append((
        (),          # discard_indices
        0,           # k
        w, l, t,     # wins, losses, ties
        baseline_total,
        baseline_wpct,
        0.0, 100.0, 0.0,       # p_improve, p_same, p_worsen
        h1_rank, h1_rank,       # best_rank, worst_rank
        baseline_wpct, baseline_wpct,  # best/worst draw win%
    ))

    # ── k=1 through k=5 ──────────────────────────────────────────
    for k in range(1, 6):
        for dp in itertools.combinations(range(5), k):
            kept = [h1[i] for i in range(5) if i not in dp]
            discarded = [h1[i] for i in dp]

            # Never discard the Joker
            if ji in discarded:
                continue

            km = 0
            for i in kept:
                km |= (1 << i)

            tw = tl = tt = 0
            imp = same = worse = 0
            br = 9     # best new rank (lower = better)
            wr = 0     # worst new rank
            bdw = -1.0   # best draw win%
            wdw = 101.0  # worst draw win%

            for draw in itertools.combinations(pool, k):
                dm = 0
                for i in draw:
                    dm |= (1 << i)
                nm = km | dm
                nk = ka[nm]
                nr = ra[nm]

                # Hand category improvement tracking
                if nr < h1_rank:
                    imp += 1
                elif nr > h1_rank:
                    worse += 1
                else:
                    same += 1

                if nr < br:
                    br = nr
                if nr > wr:
                    wr = nr

                # Count wins/losses/ties vs all opponent hands from reduced pool
                rp = [i for i in pool if not (dm & (1 << i))]

                dw = dl = dt = 0
                for a, b, c, d, e in itertools.combinations(rp, 5):
                    ok = ka[(1 << a) | (1 << b) | (1 << c) | (1 << d) | (1 << e)]
                    if nk > ok:
                        dw += 1
                    elif nk < ok:
                        dl += 1
                    else:
                        dt += 1

                tw += dw
                tl += dl
                tt += dt

                # Per-draw win %
                dtot = dw + dl + dt
                if dtot > 0:
                    dwp = dw / dtot * 100
                    if dwp > bdw:
                        bdw = dwp
                    if dwp < wdw:
                        wdw = dwp

            tot = tw + tl + tt
            td = imp + same + worse

            results.append((
                tuple(discarded),
                k,
                tw, tl, tt, tot,
                tw / tot * 100 if tot > 0 else 0,
                imp / td * 100 if td > 0 else 0,
                same / td * 100 if td > 0 else 0,
                worse / td * 100 if td > 0 else 0,
                br, wr,
                bdw, wdw,
            ))

    return (h1, baseline_wpct, results)


# Result tuple field indices
_DISC  = 0   # discard_indices
_K     = 1
_W     = 2
_L     = 3
_T     = 4
_TOT   = 5
_WPCT  = 6
_PIMP  = 7
_PSAM  = 8
_PWOR  = 9
_BRANK = 10
_WRANK = 11
_BDW   = 12
_WDW   = 13


def main():
    print("=" * 70)
    print("  21 Card Poker — Optimal Discard Calculator (Turn 2)")
    print("=" * 70)

    # ── Phase 1: Build deck & precompute hand data ────────────────

    deck = build_deck()
    n = len(deck)
    assert n == 21
    joker_idx = next(i for i, c in enumerate(deck) if c.is_joker)

    all_hands = list(itertools.combinations(range(n), 5))
    total_hands = len(all_hands)

    print(f"\nDeck: {n} cards, Joker at index {joker_idx}")
    print(f"Total 5-card hands: C({n},5) = {total_hands:,}")

    print("\nPhase 1 — Precomputing hand evaluations …")
    t0 = time.time()

    mask_size = 1 << n  # 2^21 = 2,097,152
    key_arr = [0] * mask_size
    rank_arr = [0] * mask_size

    for combo in all_hands:
        mask = 0
        for i in combo:
            mask |= (1 << i)
        cards = [deck[i] for i in combo]
        score, name, _ = evaluate_player_hand(cards)
        key_arr[mask] = score_to_key(score)
        rank_arr[mask] = score[0]

    t1 = time.time()
    print(f"  ✓ {total_hands:,} hands evaluated in {t1 - t0:.1f}s")

    # ── Phase 2: Analyze discard options (parallel) ───────────────

    num_workers = max(1, cpu_count() - 1)
    print(f"\nPhase 2 — Analyzing discard options ({num_workers} workers) …")
    print(f"  ~19 million scenarios per hand × {total_hands:,} hands")

    t2 = time.time()
    all_results = []
    completed = 0

    with Pool(
        processes=num_workers,
        initializer=_init_worker,
        initargs=(key_arr, rank_arr, joker_idx),
    ) as pool:
        for result in pool.imap_unordered(_analyze_hand, all_hands, chunksize=50):
            all_results.append(result)
            completed += 1
            if completed % 500 == 0 or completed == total_hands:
                elapsed = time.time() - t2
                rate = completed / max(elapsed, 0.001)
                eta = (total_hands - completed) / max(rate, 0.001)
                print(
                    f"  [{completed:>6,}/{total_hands:,}]"
                    f"  {completed / total_hands * 100:5.1f}%"
                    f"  elapsed {elapsed:>7.0f}s"
                    f"  ETA {eta:>7.0f}s"
                    f"  ({rate:.1f} hands/s)"
                )

    t3 = time.time()
    print(f"\n  ✓ Analysis complete in {t3 - t2:.1f}s")

    # ── Phase 3: Write CSV files ──────────────────────────────────

    print("\nPhase 3 — Writing CSV files …")

    csv_full = "data/discard_analysis.csv"
    csv_optimal = "data/optimal_discard.csv"
    csv_summary = "data/discard_summary_by_type.csv"

    rows_full = []
    rows_optimal = []

    for h1, baseline_wpct, discard_list in all_results:
        hand_str = hand_to_str([deck[i] for i in h1])
        h1_mask = 0
        for i in h1:
            h1_mask |= (1 << i)
        h1_type = HAND_NAMES.get(rank_arr[h1_mask], "Unknown")

        # Find optimal discard option (highest win%, prefer lower k as tiebreaker)
        best_r = max(discard_list, key=lambda r: (r[_WPCT], -r[_K]))

        for r in discard_list:
            # Format discard cards
            if r[_K] == 0:
                discard_str = "—"
            else:
                discard_str = hand_to_str([deck[i] for i in r[_DISC]])

            delta = r[_WPCT] - baseline_wpct

            # Risk metrics
            if r[_K] == 0:
                risk_ratio = "—"
            else:
                upside = r[_BDW] - baseline_wpct
                downside = baseline_wpct - r[_WDW]
                risk_ratio = f"{upside / max(downside, 0.01):.2f}"

            best_type = HAND_NAMES.get(r[_BRANK], "Unknown")
            worst_type = HAND_NAMES.get(r[_WRANK], "Unknown")

            rows_full.append((
                hand_str, h1_type,
                f"{baseline_wpct:.2f}",
                discard_str, r[_K],
                f"{r[_WPCT]:.2f}",
                f"{delta:.2f}",
                f"{r[_PIMP]:.2f}",
                f"{r[_PSAM]:.2f}",
                f"{r[_PWOR]:.2f}",
                best_type, worst_type,
                risk_ratio,
            ))

        # Optimal discard row
        opt = best_r
        if opt[_K] == 0:
            opt_discard_str = "—"
            verdict = "Keep"
            opt_rr = "—"
        else:
            opt_discard_str = hand_to_str([deck[i] for i in opt[_DISC]])
            opt_delta = opt[_WPCT] - baseline_wpct
            verdict = f"Discard {opt_discard_str}" if opt_delta > 0 else "Keep"
            upside = opt[_BDW] - baseline_wpct
            downside = baseline_wpct - opt[_WDW]
            opt_rr = f"{upside / max(downside, 0.01):.2f}"

        rows_optimal.append((
            hand_str, h1_type,
            baseline_wpct,
            opt_discard_str,
            opt[_WPCT],
            opt[_WPCT] - baseline_wpct,
            opt[_PIMP],
            opt_rr,
            verdict,
        ))

    # Sort full results by hand string, then by post-discard win% descending
    rows_full.sort(key=lambda r: (r[0], -float(r[5])))

    with open(csv_full, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hand", "Hand Type", "Pre-Discard Win %", "Discard",
            "Cards Discarded (k)", "Post-Discard Win %", "Delta %",
            "P(Improve)", "P(Same)", "P(Worsen)",
            "Best Outcome", "Worst Outcome", "Risk Ratio",
        ])
        writer.writerows(rows_full)

    print(f"  ✓ Wrote {len(rows_full):,} rows to {csv_full}")

    # Sort optimal by win% descending
    rows_optimal.sort(key=lambda r: (-r[4], r[0]))

    with open(csv_optimal, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hand", "Hand Type", "Pre-Discard Win %",
            "Optimal Discard", "Optimal Win %", "Delta %",
            "P(Improve)", "Risk Ratio", "Verdict",
        ])
        for r in rows_optimal:
            writer.writerow([
                r[0], r[1],
                f"{r[2]:.2f}",
                r[3],
                f"{r[4]:.2f}",
                f"{r[5]:.2f}",
                f"{r[6]:.2f}",
                r[7],
                r[8],
            ])

    print(f"  ✓ Wrote {len(rows_optimal):,} rows to {csv_optimal}")

    # ── Phase 4: Summary by hand type ─────────────────────────────

    type_data = defaultdict(list)
    for r in rows_optimal:
        type_data[r[1]].append(r)

    summary = []
    for hand_type, entries in type_data.items():
        n_entries = len(entries)
        discard_helps = sum(1 for e in entries if e[5] > 0)

        # Determine most common optimal k
        k_values = []
        for e in entries:
            if e[3] == "—":
                k_values.append(0)
            else:
                k_values.append(len(e[3].split()))
        most_common_k = Counter(k_values).most_common(1)[0][0]

        summary.append({
            "type": hand_type,
            "count": n_entries,
            "avg_pre": sum(e[2] for e in entries) / n_entries,
            "avg_optimal": sum(e[4] for e in entries) / n_entries,
            "avg_delta": sum(e[5] for e in entries) / n_entries,
            "pct_helps": discard_helps / n_entries * 100,
            "common_k": most_common_k,
        })

    summary.sort(key=lambda s: -s["avg_pre"])

    with open(csv_summary, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hand Type", "Count", "Avg Pre-Discard Win %",
            "Avg Optimal Win %", "Avg Delta %",
            "% Hands Where Discard Helps", "Most Common Optimal k",
        ])
        for s in summary:
            writer.writerow([
                s["type"], s["count"],
                f'{s["avg_pre"]:.2f}',
                f'{s["avg_optimal"]:.2f}',
                f'{s["avg_delta"]:.2f}',
                f'{s["pct_helps"]:.1f}',
                s["common_k"],
            ])

    print(f"  ✓ Wrote {len(summary)} rows to {csv_summary}")

    # ── Console summary ───────────────────────────────────────────

    print("\n" + "=" * 90)
    print("  DISCARD STRATEGY SUMMARY BY HAND TYPE")
    print("=" * 90)
    header = (
        f"  {'Hand Type':<20} {'Count':>6}"
        f" {'Avg Pre%':>9} {'Avg Opt%':>9} {'Avg Δ%':>8}"
        f" {'Disc Helps%':>12} {'Common k':>9}"
    )
    print(header)
    print("  " + "-" * 86)
    for s in summary:
        print(
            f"  {s['type']:<20} {s['count']:>6}"
            f" {s['avg_pre']:>8.2f}% {s['avg_optimal']:>8.2f}% {s['avg_delta']:>+7.2f}%"
            f" {s['pct_helps']:>11.1f}% {s['common_k']:>9}"
        )

    # Top 15 hands where discard helps most
    discard_winners = [r for r in rows_optimal if r[5] > 0]
    discard_winners.sort(key=lambda r: -r[5])

    print("\n" + "=" * 90)
    print("  TOP 15 HANDS WHERE DISCARD HELPS MOST (by Δ Win %)")
    print("=" * 90)
    print(
        f"  {'#':>4}  {'Hand':<20} {'Type':<20}"
        f" {'Pre%':>7} {'Opt%':>7} {'Δ%':>7}  {'Optimal Discard'}"
    )
    print("  " + "-" * 86)
    for i, r in enumerate(discard_winners[:15], 1):
        print(
            f"  {i:>4}  {r[0]:<20} {r[1]:<20}"
            f" {r[2]:>6.2f}% {r[4]:>6.2f}% {r[5]:>+6.2f}%  {r[3]}"
        )

    # Hands where keeping is optimal despite discard being possible
    keepers = [r for r in rows_optimal if r[5] <= 0]
    print(
        f"\n  Hands where 'Keep' is optimal: {len(keepers):,} / {len(rows_optimal):,}"
        f" ({len(keepers) / len(rows_optimal) * 100:.1f}%)"
    )
    discarders = len(rows_optimal) - len(keepers)
    print(
        f"  Hands where discard improves EV: {discarders:,} / {len(rows_optimal):,}"
        f" ({discarders / len(rows_optimal) * 100:.1f}%)"
    )

    total_time = time.time() - t0
    print(f"\n  Total time: {total_time:.1f}s")
    print(f"\n  Output files:")
    print(f"    {csv_full:<35} — All {len(rows_full):,} discard options")
    print(f"    {csv_optimal:<35} — Optimal strategy per hand ({len(rows_optimal):,} rows)")
    print(f"    {csv_summary:<35} — Summary by hand type ({len(summary)} rows)")
    print()


if __name__ == "__main__":
    main()
