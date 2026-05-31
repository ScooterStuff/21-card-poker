"""
21 Card Poker — Meta-Strategy Statistical Explorer

Computes the information and deception layer of the game:
  Part A: Opponent Read Table — P(Hand Type | opponent discards k)
  Part B: Information Advantage — entropy/certainty per discard choice
  Part C: Deception Cost — win% sacrifice for bluffing with non-optimal k
  Part D: Post-Draw Opponent Model — Bayesian win% given observed opponent k

Prerequisites: discard_calculator.py must have been run first
  (needs optimal_discard.csv and discard_analysis.csv)

Output:
  read_table.csv             — P(Hand Type | k) for each k
  information_advantage.csv  — Entropy/certainty per hand × k
  deception_cost.csv         — Per-hand cost of each alternative k
  deception_summary.csv      — Avg bluff cost by hand type
  post_draw_model.csv        — Bayesian win% per hand × opponent k

Usage:
  python meta_strategy_calculator.py
"""

import csv
import itertools
import math
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool, cpu_count

from core.hand_eval import evaluate_player_hand, HAND_NAMES
from .probability_calculator import build_deck, score_to_key, hand_to_str

# Hand rank constants (matching hand_eval.py)
RANK_ORDER = [1, 2, 3, 4, 5, 6, 7, 8]  # Five of a Kind .. Pair
STRONG_THRESHOLD = 5   # ranks 1–5 are "strong" (Five of Kind through Straight)

# CLI flag: skip expensive Parts B & D
SKIP_BD = "--fast" in sys.argv


# ── Helpers ───────────────────────────────────────────────────────

def entropy(counts: dict) -> float:
    """Shannon entropy in bits from a dict of {label: count}."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h


def load_optimal_discard(path="data/optimal_discard.csv"):
    """Load optimal_discard.csv into list of dicts."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_discard_analysis(path="data/discard_analysis.csv"):
    """Load discard_analysis.csv into list of dicts."""
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def optimal_k_from_row(row):
    """Extract the optimal k from an optimal_discard row."""
    discard_str = row["Optimal Discard"]
    if discard_str == "\u2014" or discard_str == "—" or discard_str == "-":
        return 0
    return len(discard_str.split())


def analysis_k_from_row(row):
    """Extract k from a discard_analysis row."""
    return int(row["Cards Discarded (k)"])


# ── Shared worker state for Parts B & D ──────────────────────────

_key_arr = None
_rank_arr = None
_joker_idx_w = None
_rt_weights = None  # read_table_weights for Part D


def _init_worker_bd(key_arr, rank_arr, joker_idx, rt_weights):
    global _key_arr, _rank_arr, _joker_idx_w, _rt_weights
    _key_arr = key_arr
    _rank_arr = rank_arr
    _joker_idx_w = joker_idx
    _rt_weights = rt_weights


def _compute_info_advantage(h1):
    """Compute information advantage metrics for one starting hand.

    For each k (0..5), we compute:
      - Entropy of opponent hand type distribution (averaged across draw outcomes)
      - Certainty% and ambiguity% across (discard subset × draw) outcomes

    Optimization: for each draw combo, opponent keys are computed ONCE and
    reused across all discard subsets of size k.
    """
    ka = _key_arr
    ra = _rank_arr
    ji = _joker_idx_w

    hm = 0
    for i in h1:
        hm |= (1 << i)
    h1_key = ka[hm]
    h1_rank = ra[hm]

    pool = [i for i in range(21) if not (hm & (1 << i))]

    results = []

    # k=0: single scenario (original hand vs all opponents)
    opp_type_counts = defaultdict(int)
    wins = 0
    total_opp = 0
    for opp in itertools.combinations(pool, 5):
        om = (1 << opp[0]) | (1 << opp[1]) | (1 << opp[2]) | (1 << opp[3]) | (1 << opp[4])
        ok = ka[om]
        opp_type_counts[ra[om]] += 1
        total_opp += 1
        if h1_key > ok:
            wins += 1

    ent0 = entropy(opp_type_counts)
    wpct0 = wins / total_opp * 100
    cert0 = 100.0 if (wpct0 > 80 or wpct0 < 20) else 0.0
    ambig0 = 100.0 if (40 <= wpct0 <= 60) else 0.0

    results.append((0, wpct0, 16, total_opp, ent0, 0.0, cert0, ambig0))

    # k=1..5
    non_joker_pos = [i for i in range(5) if h1[i] != ji]

    for k in range(1, 6):
        if k > len(non_joker_pos):
            continue

        # Precompute kept-card masks for all discard subsets of size k
        kept_masks = []
        for dp in itertools.combinations(non_joker_pos, k):
            km = 0
            for i in range(5):
                if i not in dp:
                    km |= (1 << h1[i])
            kept_masks.append(km)

        if not kept_masks:
            continue

        n_draw_outcomes = 0
        n_certain = 0
        n_ambiguous = 0
        ent_sum = 0.0
        overall_wins = 0
        overall_total = 0

        for draw in itertools.combinations(pool, k):
            dm = 0
            for i in draw:
                dm |= (1 << i)

            # Compute opponent keys ONCE for this draw combo
            rp = [i for i in pool if not (dm & (1 << i))]
            opp_keys = []
            opp_type_counts = defaultdict(int)
            for opp in itertools.combinations(rp, 5):
                om = (1 << opp[0]) | (1 << opp[1]) | (1 << opp[2]) | (1 << opp[3]) | (1 << opp[4])
                ok = ka[om]
                opp_keys.append(ok)
                opp_type_counts[ra[om]] += 1

            draw_ent = entropy(opp_type_counts)
            n_opp = len(opp_keys)

            # Reuse opponent keys across all discard subsets
            for km in kept_masks:
                nk = ka[km | dm]

                dw = sum(1 for ok in opp_keys if nk > ok)
                dwpct = dw / n_opp * 100

                ent_sum += draw_ent
                n_draw_outcomes += 1
                overall_wins += dw
                overall_total += n_opp

                if dwpct > 80 or dwpct < 20:
                    n_certain += 1
                if 40 <= dwpct <= 60:
                    n_ambiguous += 1

        if n_draw_outcomes == 0:
            continue

        avg_ent = ent_sum / n_draw_outcomes
        raw_ev = overall_wins / overall_total * 100
        opp_pool = 16 - k
        opp_hands = math.comb(opp_pool, 5)
        info_gain = ent0 - avg_ent

        results.append((
            k, raw_ev, opp_pool, opp_hands,
            avg_ent, info_gain,
            n_certain / n_draw_outcomes * 100,
            n_ambiguous / n_draw_outcomes * 100,
        ))

    return (h1, results)


def _compute_post_draw(h1):
    """Compute naive and Bayesian win% for one hand vs all opponents.

    Enumerates opponent hands ONCE, then applies all 6 Bayesian weight
    sets (one per opponent k) in a single pass.
    """
    ka = _key_arr
    ra = _rank_arr
    rtw = _rt_weights

    hm = 0
    for i in h1:
        hm |= (1 << i)
    h1_key = ka[hm]

    pool = [i for i in range(21) if not (hm & (1 << i))]

    # Single pass: collect all opponent data
    opp_data = []  # list of (key, hand_type_str)
    for opp in itertools.combinations(pool, 5):
        om = (1 << opp[0]) | (1 << opp[1]) | (1 << opp[2]) | (1 << opp[3]) | (1 << opp[4])
        ok = ka[om]
        ot = HAND_NAMES.get(ra[om], "Unknown")
        opp_data.append((ok, ot))

    naive_total = len(opp_data)
    naive_w = sum(1 for ok, _ in opp_data if h1_key > ok)
    naive_l = sum(1 for ok, _ in opp_data if h1_key < ok)
    naive_wpct = naive_w / naive_total * 100

    results = []
    for k_opp in range(6):
        weights = rtw.get(k_opp, {})

        bw = bl = bt = 0.0
        type_bcount = defaultdict(float)
        for ok, ot in opp_data:
            w = weights.get(ot, 1.0)
            type_bcount[ot] += w
            if h1_key > ok:
                bw += w
            elif h1_key < ok:
                bl += w
            else:
                bt += w

        btotal = bw + bl + bt
        bwpct = bw / btotal * 100 if btotal > 0 else 0
        blpct = bl / btotal * 100 if btotal > 0 else 0
        most_likely = max(type_bcount, key=type_bcount.get) if type_bcount else "Unknown"

        results.append((
            k_opp,
            naive_wpct,
            bwpct,
            bwpct - naive_wpct,
            blpct,
            most_likely,
        ))

    return (h1, results)


# ── Main ──────────────────────────────────────────────────────────

def main():
    # Ensure unbuffered output for background/piped execution
    print("=" * 70, flush=True)
    print("  21 Card Poker — Meta-Strategy Statistical Explorer", flush=True)
    print("=" * 70, flush=True)

    t0 = time.time()

    # ── Phase 1: Build deck & precompute hand data ────────────────

    deck = build_deck()
    n = len(deck)
    assert n == 21
    joker_idx = next(i for i, c in enumerate(deck) if c.is_joker)

    all_hands = list(itertools.combinations(range(n), 5))
    total_hands = len(all_hands)

    print(f"\nDeck: {n} cards, Joker at index {joker_idx}")
    print(f"Total 5-card hands: {total_hands:,}")

    print("\nPhase 1 — Precomputing hand evaluations …")
    t1 = time.time()

    mask_size = 1 << n
    key_arr = [0] * mask_size
    rank_arr = [0] * mask_size

    hand_type_map = {}  # combo tuple → hand type string
    hand_key_map = {}   # combo tuple → integer key

    for combo in all_hands:
        mask = 0
        for i in combo:
            mask |= (1 << i)
        cards = [deck[i] for i in combo]
        score, name, _ = evaluate_player_hand(cards)
        key_arr[mask] = score_to_key(score)
        rank_arr[mask] = score[0]
        hand_type_map[combo] = name
        hand_key_map[combo] = key_arr[mask]

    t1e = time.time()
    print(f"  ✓ {total_hands:,} hands evaluated in {t1e - t1:.1f}s", flush=True)

    # ── Phase 2 (Part A): Read Table ─────────────────────────────

    print("\nPhase 2 (Part A) — Computing Opponent Read Table …")
    t2 = time.time()

    opt_data = load_optimal_discard()
    print(f"  Loaded {len(opt_data):,} rows from optimal_discard.csv")

    # Group by optimal k
    k_groups = defaultdict(list)
    for row in opt_data:
        k = optimal_k_from_row(row)
        k_groups[k].append(row)

    read_table_rows = []
    read_table_weights = {}  # k → {hand_type: weight} for Part D

    for k in range(6):
        group = k_groups.get(k, [])
        if not group:
            continue

        type_counts = Counter(row["Hand Type"] for row in group)
        total_in_k = len(group)

        # Pre/post discard averages by type
        type_pre = defaultdict(list)
        type_post = defaultdict(list)
        for row in group:
            ht = row["Hand Type"]
            type_pre[ht].append(float(row["Pre-Discard Win %"]))
            type_post[ht].append(float(row["Optimal Win %"]))

        # Compute weights for Bayesian usage (Part D)
        weights_for_k = {}
        for ht, count in type_counts.items():
            weights_for_k[ht] = count / total_in_k

        read_table_weights[k] = weights_for_k

        # Derived metrics
        p_strong = sum(c for ht, c in type_counts.items()
                       if HAND_NAMES.get(next((r for r, n in HAND_NAMES.items() if n == ht), 99), "") == ht
                       and next((r for r, n in HAND_NAMES.items() if n == ht), 99) <= STRONG_THRESHOLD) / total_in_k * 100

        # Simpler: look up rank from HAND_NAMES
        name_to_rank = {v: k_ for k_, v in HAND_NAMES.items()}
        p_strong = sum(c for ht, c in type_counts.items()
                       if name_to_rank.get(ht, 99) <= STRONG_THRESHOLD) / total_in_k * 100
        p_weak = 100 - p_strong

        avg_post_all = sum(float(r["Optimal Win %"]) for r in group) / total_in_k
        ent = entropy(type_counts)

        for ht in sorted(type_counts.keys(), key=lambda x: name_to_rank.get(x, 99)):
            count = type_counts[ht]
            avg_pre = sum(type_pre[ht]) / len(type_pre[ht])
            avg_post = sum(type_post[ht]) / len(type_post[ht])
            read_table_rows.append({
                "k": k,
                "hand_type": ht,
                "count": count,
                "p_type_given_k": count / total_in_k * 100,
                "avg_pre_win": avg_pre,
                "avg_post_win": avg_post,
            })

        # Add a summary row for this k
        read_table_rows.append({
            "k": k,
            "hand_type": f"[ALL k={k}]",
            "count": total_in_k,
            "p_type_given_k": 100.0,
            "avg_pre_win": sum(float(r["Pre-Discard Win %"]) for r in group) / total_in_k,
            "avg_post_win": avg_post_all,
            "_p_strong": p_strong,
            "_p_weak": p_weak,
            "_entropy": ent,
        })

    # Write read_table.csv
    with open("data/read_table.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Opponent k", "Hand Type", "Count", "P(Hand Type | k) %",
            "Avg Pre-Discard Win %", "Avg Post-Discard Win %",
            "P(Strong | k) %", "P(Weak | k) %", "Entropy (bits)",
        ])
        for r in read_table_rows:
            writer.writerow([
                r["k"], r["hand_type"], r["count"],
                f'{r["p_type_given_k"]:.2f}',
                f'{r["avg_pre_win"]:.2f}',
                f'{r["avg_post_win"]:.2f}',
                f'{r.get("_p_strong", ""):.2f}' if "_p_strong" in r else "",
                f'{r.get("_p_weak", ""):.2f}' if "_p_weak" in r else "",
                f'{r.get("_entropy", ""):.3f}' if "_entropy" in r else "",
            ])

    t2e = time.time()
    print(f"  ✓ Wrote {len(read_table_rows)} rows to read_table.csv in {t2e - t2:.1f}s", flush=True)

    # Print read table to console
    print("\n  OPPONENT READ TABLE — P(Hand Type | Opponent Discards k)")
    print("  " + "-" * 80)
    print(f"  {'k':>3}  {'Hand Type':<20} {'Count':>6} {'P(Type|k)':>10}"
          f" {'Avg Pre%':>9} {'Avg Post%':>10}")
    print("  " + "-" * 80)
    for r in read_table_rows:
        if r["hand_type"].startswith("[ALL"):
            print("  " + "-" * 80)
            print(f"  {r['k']:>3}  {r['hand_type']:<20} {r['count']:>6}"
                  f" {'':>10} {r['avg_pre_win']:>8.2f}% {r['avg_post_win']:>9.2f}%"
                  f"  P(strong)={r.get('_p_strong', 0):.1f}%"
                  f"  entropy={r.get('_entropy', 0):.3f} bits")
            print()
        else:
            print(f"  {r['k']:>3}  {r['hand_type']:<20} {r['count']:>6}"
                  f" {r['p_type_given_k']:>9.2f}% {r['avg_pre_win']:>8.2f}%"
                  f" {r['avg_post_win']:>9.2f}%")

    # ── Phase 3 (Part C): Deception Cost ─────────────────────────

    print("\nPhase 3 (Part C) — Computing Deception Cost …")
    t3 = time.time()

    analysis_data = load_discard_analysis()
    print(f"  Loaded {len(analysis_data):,} rows from discard_analysis.csv")

    # Group analysis data by hand
    hand_analysis = defaultdict(list)
    for row in analysis_data:
        hand_analysis[row["Hand"]].append(row)

    # Build optimal lookup: hand → (optimal_k, optimal_win%)
    opt_lookup = {}
    for row in opt_data:
        hand = row["Hand"]
        opt_k = optimal_k_from_row(row)
        opt_wpct = float(row["Optimal Win %"])
        opt_lookup[hand] = (opt_k, opt_wpct)

    deception_rows = []

    for hand, analyses in hand_analysis.items():
        opt_k, opt_wpct = opt_lookup.get(hand, (0, 0))
        hand_type = analyses[0]["Hand Type"]

        # Find best win% for each k value
        best_by_k = {}
        for row in analyses:
            row_k = analysis_k_from_row(row)
            row_wpct = float(row["Post-Discard Win %"])
            if row_k not in best_by_k or row_wpct > best_by_k[row_k]:
                best_by_k[row_k] = row_wpct

        for alt_k in range(6):
            if alt_k == opt_k:
                continue
            if alt_k not in best_by_k:
                continue
            alt_wpct = best_by_k[alt_k]
            cost = opt_wpct - alt_wpct

            deception_rows.append({
                "hand": hand,
                "hand_type": hand_type,
                "opt_k": opt_k,
                "opt_wpct": opt_wpct,
                "alt_k": alt_k,
                "alt_wpct": alt_wpct,
                "cost": cost,
            })

    # Write deception_cost.csv
    with open("data/deception_cost.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hand", "Hand Type", "Optimal k", "Optimal Win %",
            "Alternative k", "Alternative Win %", "Deception Cost (Δ%)",
        ])
        for r in sorted(deception_rows, key=lambda x: (x["hand"], x["alt_k"])):
            writer.writerow([
                r["hand"], r["hand_type"], r["opt_k"],
                f'{r["opt_wpct"]:.2f}', r["alt_k"],
                f'{r["alt_wpct"]:.2f}', f'{r["cost"]:.2f}',
            ])

    print(f"  ✓ Wrote {len(deception_rows):,} rows to deception_cost.csv", flush=True)

    # Deception summary by hand type
    name_to_rank = {v: k_ for k_, v in HAND_NAMES.items()}
    type_deception = defaultdict(lambda: defaultdict(list))
    type_opt_k = defaultdict(list)

    for r in deception_rows:
        type_deception[r["hand_type"]][r["alt_k"]].append(r["cost"])

    for hand, (opt_k, _) in opt_lookup.items():
        ht = hand_analysis[hand][0]["Hand Type"] if hand in hand_analysis else "Unknown"
        type_opt_k[ht].append(opt_k)

    summary_rows = []
    for ht in sorted(type_deception.keys(), key=lambda x: name_to_rank.get(x, 99)):
        alt_costs = type_deception[ht]
        n_hands = len(type_opt_k[ht])
        mode_k = Counter(type_opt_k[ht]).most_common(1)[0][0]

        row = {
            "hand_type": ht,
            "count": n_hands,
            "mode_k": mode_k,
        }

        # Average cost for each alternative k
        cheapest_k = None
        cheapest_cost = float("inf")
        for alt_k in range(6):
            costs = alt_costs.get(alt_k, [])
            if costs:
                avg = sum(costs) / len(costs)
                row[f"avg_cost_k{alt_k}"] = avg
                if alt_k != mode_k and avg < cheapest_cost:
                    cheapest_cost = avg
                    cheapest_k = alt_k
            else:
                row[f"avg_cost_k{alt_k}"] = None

        row["cheapest_bluff_k"] = cheapest_k
        row["cheapest_bluff_cost"] = cheapest_cost if cheapest_cost < float("inf") else None

        # % hands where cheapest bluff < 1%
        if cheapest_k is not None:
            costs_for_cheapest = alt_costs.get(cheapest_k, [])
            under_1 = sum(1 for c in costs_for_cheapest if c < 1.0)
            row["pct_bluff_under_1"] = under_1 / len(costs_for_cheapest) * 100 if costs_for_cheapest else 0
        else:
            row["pct_bluff_under_1"] = 0

        summary_rows.append(row)

    with open("data/deception_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Hand Type", "Count", "Optimal k (mode)",
            "Avg Cost k=0", "Avg Cost k=1", "Avg Cost k=2",
            "Avg Cost k=3", "Avg Cost k=4", "Avg Cost k=5",
            "Cheapest Bluff k", "Avg Cheapest Bluff Cost",
            "% Hands Bluff < 1%",
        ])
        for r in summary_rows:
            writer.writerow([
                r["hand_type"], r["count"], r["mode_k"],
                f'{r["avg_cost_k0"]:.2f}' if r["avg_cost_k0"] is not None else "N/A",
                f'{r["avg_cost_k1"]:.2f}' if r["avg_cost_k1"] is not None else "N/A",
                f'{r["avg_cost_k2"]:.2f}' if r["avg_cost_k2"] is not None else "N/A",
                f'{r["avg_cost_k3"]:.2f}' if r["avg_cost_k3"] is not None else "N/A",
                f'{r["avg_cost_k4"]:.2f}' if r["avg_cost_k4"] is not None else "N/A",
                f'{r["avg_cost_k5"]:.2f}' if r["avg_cost_k5"] is not None else "N/A",
                r["cheapest_bluff_k"] if r["cheapest_bluff_k"] is not None else "N/A",
                f'{r["cheapest_bluff_cost"]:.2f}' if r["cheapest_bluff_cost"] is not None else "N/A",
                f'{r["pct_bluff_under_1"]:.1f}',
            ])

    t3e = time.time()
    print(f"  ✓ Wrote {len(summary_rows)} rows to deception_summary.csv in {t3e - t3:.1f}s")

    # Print deception summary
    print("\n  DECEPTION COST SUMMARY BY HAND TYPE")
    print("  " + "-" * 95)
    print(f"  {'Hand Type':<20} {'Count':>6} {'Opt k':>5}"
          f" {'→k=0':>7} {'→k=1':>7} {'→k=2':>7} {'→k=3':>7} {'→k=4':>7} {'→k=5':>7}"
          f"  {'Cheap k':>7} {'Cost':>6} {'<1%':>5}")
    print("  " + "-" * 95)
    for r in summary_rows:
        costs = []
        for kk in range(6):
            v = r[f"avg_cost_k{kk}"]
            if v is None:
                costs.append("   N/A")
            elif kk == r["mode_k"]:
                costs.append("   OPT")
            else:
                costs.append(f"{v:>6.2f}%")
        ck = r["cheapest_bluff_k"]
        cc = r["cheapest_bluff_cost"]
        print(
            f"  {r['hand_type']:<20} {r['count']:>6} {r['mode_k']:>5}"
            f" {''.join(costs)}"
            f"  {ck if ck is not None else 'N/A':>7}"
            f" {f'{cc:.2f}' if cc is not None else 'N/A':>6}"
            f" {r['pct_bluff_under_1']:>4.0f}%"
        )

    # ── Phase 4 (Part B): Information Advantage ───────────────────

    num_workers = max(1, cpu_count() - 1)
    ia_rows = []

    if SKIP_BD:
        print("\nPhase 4 (Part B) — SKIPPED (--fast mode)", flush=True)
    else:
        print(f"\nPhase 4 (Part B) — Computing Information Advantage ({num_workers} workers) …", flush=True)
        t4 = time.time()

        info_results = []
        completed = 0

        with Pool(
            processes=num_workers,
            initializer=_init_worker_bd,
            initargs=(key_arr, rank_arr, joker_idx, {}),
        ) as pool:
            for h1, results in pool.imap_unordered(_compute_info_advantage, all_hands, chunksize=50):
                info_results.append((h1, results))
                completed += 1
                if completed % 2000 == 0 or completed == total_hands:
                    elapsed = time.time() - t4
                    rate = completed / max(elapsed, 0.001)
                    eta = (total_hands - completed) / max(rate, 0.001)
                    print(
                        f"  [{completed:>6,}/{total_hands:,}]"
                        f"  {completed / total_hands * 100:5.1f}%"
                        f"  elapsed {elapsed:>6.0f}s  ETA {eta:>6.0f}s",
                        flush=True,
                    )

        # Write information_advantage.csv
        for h1, results in info_results:
            hand_str = hand_to_str([deck[i] for i in h1])
            ht = hand_type_map[h1]
            for r in results:
                ia_rows.append((
                    hand_str, ht,
                    r[0],   # k
                    r[1],   # raw EV
                    r[2],   # opp pool size
                    r[3],   # opp hands
                    r[4],   # entropy
                    r[5],   # info gain
                    r[6],   # certainty%
                    r[7],   # ambiguity%
                ))

        ia_rows.sort(key=lambda x: (x[0], x[2]))

        with open("data/information_advantage.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Hand", "Hand Type", "k", "Raw EV (Win %)",
                "Opponent Pool Size", "Opponent Hands",
                "Entropy (bits)", "Info Gain vs k=0 (bits)",
                "Certainty %", "Ambiguity %",
            ])
            for r in ia_rows:
                writer.writerow([
                    r[0], r[1], r[2],
                    f"{r[3]:.2f}", r[4], r[5],
                    f"{r[6]:.3f}", f"{r[7]:.3f}",
                    f"{r[8]:.1f}", f"{r[9]:.1f}",
                ])

        t4e = time.time()
        print(f"  ✓ Wrote {len(ia_rows):,} rows to information_advantage.csv in {t4e - t4:.1f}s")

        # Print info advantage summary (avg by k)
        k_entropy = defaultdict(list)
        k_certainty = defaultdict(list)
        k_ambiguity = defaultdict(list)
        for r in ia_rows:
            k_entropy[r[2]].append(r[6])
            k_certainty[r[2]].append(r[8])
            k_ambiguity[r[2]].append(r[9])

        print("\n  INFORMATION ADVANTAGE SUMMARY (averaged across all hands)")
        print("  " + "-" * 70)
        print(f"  {'k':>3}  {'Pool':>5}  {'Opp Hands':>10}  {'Avg Entropy':>12}"
              f"  {'Avg Certainty%':>15}  {'Avg Ambiguity%':>15}")
        print("  " + "-" * 70)
        for k in sorted(k_entropy.keys()):
            avg_ent = sum(k_entropy[k]) / len(k_entropy[k])
            avg_cert = sum(k_certainty[k]) / len(k_certainty[k])
            avg_amb = sum(k_ambiguity[k]) / len(k_ambiguity[k])
            print(f"  {k:>3}  {16-k:>5}  {math.comb(16-k, 5):>10,}"
                  f"  {avg_ent:>11.3f}b  {avg_cert:>14.1f}%  {avg_amb:>14.1f}%")

    # ── Phase 5 (Part D): Post-Draw Opponent Model ────────────────

    pd_rows = []

    if SKIP_BD:
        print("\nPhase 5 (Part D) — SKIPPED (--fast mode)", flush=True)
    else:
        print(f"\nPhase 5 (Part D) — Computing Post-Draw Opponent Model ({num_workers} workers) …", flush=True)
        t5 = time.time()

        pd_results = []
        completed = 0

        with Pool(
            processes=num_workers,
            initializer=_init_worker_bd,
            initargs=(key_arr, rank_arr, joker_idx, read_table_weights),
        ) as pool:
            for h1, results in pool.imap_unordered(_compute_post_draw, all_hands, chunksize=100):
                pd_results.append((h1, results))
                completed += 1
                if completed % 2000 == 0 or completed == total_hands:
                    elapsed = time.time() - t5
                    rate = completed / max(elapsed, 0.001)
                    eta = (total_hands - completed) / max(rate, 0.001)
                    print(
                        f"  [{completed:>6,}/{total_hands:,}]"
                        f"  {completed / total_hands * 100:5.1f}%"
                        f"  elapsed {elapsed:>6.0f}s  ETA {eta:>6.0f}s",
                        flush=True,
                    )

        # Write post_draw_model.csv
        for h1, results in pd_results:
            hand_str = hand_to_str([deck[i] for i in h1])
            ht = hand_type_map[h1]
            for r in results:
                pd_rows.append((
                    hand_str, ht,
                    r[0],   # opponent k
                    r[1],   # naive win%
                    r[2],   # bayesian win%
                    r[3],   # delta
                    r[4],   # P(opp stronger) bayesian
                    r[5],   # most likely opp type
                ))

        pd_rows.sort(key=lambda x: (x[0], x[2]))

        with open("data/post_draw_model.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Your Hand", "Your Hand Type", "Opponent k",
                "Naive Win %", "Bayesian Win %", "Δ (Bayes − Naive) %",
                "P(Opp Stronger) %", "Most Likely Opp Type",
            ])
            for r in pd_rows:
                writer.writerow([
                    r[0], r[1], r[2],
                    f"{r[3]:.2f}", f"{r[4]:.2f}", f"{r[5]:.2f}",
                    f"{r[6]:.2f}", r[7],
                ])

        t5e = time.time()
        print(f"  ✓ Wrote {len(pd_rows):,} rows to post_draw_model.csv in {t5e - t5:.1f}s")

        # Print Bayesian shift summary
        print("\n  BAYESIAN SHIFT SUMMARY (avg Δ between Bayes and Naive win%)")
        print("  " + "-" * 60)
        print(f"  {'Opp k':>6}  {'Avg Naive Win%':>15}  {'Avg Bayes Win%':>15}  {'Avg Δ':>8}")
        print("  " + "-" * 60)
        k_naive = defaultdict(list)
        k_bayes = defaultdict(list)
        k_delta = defaultdict(list)
        for r in pd_rows:
            k_naive[r[2]].append(r[3])
            k_bayes[r[2]].append(r[4])
            k_delta[r[2]].append(r[5])
        for k in sorted(k_naive.keys()):
            an = sum(k_naive[k]) / len(k_naive[k])
            ab = sum(k_bayes[k]) / len(k_bayes[k])
            ad = sum(k_delta[k]) / len(k_delta[k])
            print(f"  {k:>6}  {an:>14.2f}%  {ab:>14.2f}%  {ad:>+7.2f}%")

    # ── Final summary ─────────────────────────────────────────────

    total_time = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  Total time: {total_time:.1f}s")
    print(f"\n  Output files:")
    print(f"    {'read_table.csv':<35} — P(Hand Type | k) ({len(read_table_rows)} rows)")
    print(f"    {'deception_cost.csv':<35} — Per-hand bluff costs ({len(deception_rows):,} rows)")
    print(f"    {'deception_summary.csv':<35} — Bluff cost by hand type ({len(summary_rows)} rows)")
    if ia_rows:
        print(f"    {'information_advantage.csv':<35} — Entropy & certainty ({len(ia_rows):,} rows)")
    if pd_rows:
        print(f"    {'post_draw_model.csv':<35} — Bayesian win% ({len(pd_rows):,} rows)")
    print()


if __name__ == "__main__":
    main()
