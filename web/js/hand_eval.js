// 21 Card Poker — Hand evaluation and comparison

import { Card, RANKS, SUITS, RANK_VALUES } from "./game.js";

export const FIVE_OF_A_KIND = 1;
export const ROYAL_FLUSH = 2;
export const FOUR_OF_A_KIND = 3;
export const FULL_HOUSE = 4;
export const STRAIGHT = 5;
export const THREE_OF_A_KIND = 6;
export const TWO_PAIR = 7;
export const PAIR = 8;

export const HAND_NAMES = {
  [FIVE_OF_A_KIND]: "Five of a Kind",
  [ROYAL_FLUSH]: "Royal Flush",
  [FOUR_OF_A_KIND]: "Four of a Kind",
  [FULL_HOUSE]: "Full House",
  [STRAIGHT]: "Straight",
  [THREE_OF_A_KIND]: "Three of a Kind",
  [TWO_PAIR]: "Two Pair",
  [PAIR]: "Pair",
};

const rv = (r) => RANK_VALUES[r] ?? 0;

export function evaluateHandNoJoker(cards) {
  const ranks = cards.map((c) => c.rank);
  const suits = cards.map((c) => c.suit);
  const counts = {};
  for (const r of ranks) counts[r] = (counts[r] || 0) + 1;
  const sorted = Object.entries(counts).sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1];
    return rv(b[0]) - rv(a[0]);
  });

  if (sorted[0][1] === 5) return [FIVE_OF_A_KIND, rv(sorted[0][0])];

  const uniqSuits = new Set(suits);
  const uniqRanks = new Set(ranks);
  const royalSet = new Set(["A", "K", "Q", "J", "10"]);
  const isRoyalRanks =
    uniqRanks.size === 5 && [...uniqRanks].every((r) => royalSet.has(r));

  if (uniqSuits.size === 1 && isRoyalRanks) return [ROYAL_FLUSH];

  if (sorted[0][1] === 4) {
    return [FOUR_OF_A_KIND, rv(sorted[0][0]), rv(sorted[1][0])];
  }

  if (sorted[0][1] === 3 && sorted[1][1] === 2) {
    return [FULL_HOUSE, rv(sorted[0][0]), rv(sorted[1][0])];
  }

  if (isRoyalRanks) return [STRAIGHT];

  if (sorted[0][1] === 3) {
    const trips = rv(sorted[0][0]);
    const kickers = sorted
      .filter(([, c]) => c !== 3)
      .map(([r]) => rv(r))
      .sort((a, b) => b - a);
    return [THREE_OF_A_KIND, trips, ...kickers];
  }

  const pairs = sorted.filter(([, c]) => c === 2);
  if (pairs.length === 2) {
    const pv = pairs.map(([r]) => rv(r)).sort((a, b) => b - a);
    const kicker = sorted.filter(([, c]) => c === 1).map(([r]) => rv(r));
    return [TWO_PAIR, pv[0], pv[1], ...kicker];
  }

  if (sorted[0][1] === 2) {
    const pair = rv(sorted[0][0]);
    const kickers = sorted
      .filter(([, c]) => c === 1)
      .map(([r]) => rv(r))
      .sort((a, b) => b - a);
    return [PAIR, pair, ...kickers];
  }

  const vals = ranks.map(rv).sort((a, b) => b - a);
  return [9, ...vals];
}

export function compareScores(a, b) {
  if (a[0] !== b[0]) return a[0] < b[0] ? 1 : -1;
  const len = Math.max(a.length, b.length);
  for (let i = 1; i < len; i++) {
    const va = a[i] ?? 0;
    const vb = b[i] ?? 0;
    if (va !== vb) return va > vb ? 1 : -1;
  }
  return 0;
}

export function evaluateHandWithJoker(cards) {
  const nonJoker = cards.filter((c) => !c.isJoker);
  let bestScore = null;
  let bestCard = null;
  for (const r of RANKS) {
    for (const s of SUITS) {
      const cand = new Card(r, s);
      const score = evaluateHandNoJoker([...nonJoker, cand]);
      if (bestScore === null || compareScores(score, bestScore) > 0) {
        bestScore = score;
        bestCard = cand;
      }
    }
  }
  return [bestScore, bestCard];
}

export function evaluatePlayerHand(cards) {
  const hasJoker = cards.some((c) => c.isJoker);
  if (hasJoker) {
    const [score, resolved] = evaluateHandWithJoker(cards);
    return { score, name: HAND_NAMES[score[0]] || "Unknown", joker: resolved };
  }
  const score = evaluateHandNoJoker(cards);
  return { score, name: HAND_NAMES[score[0]] || "Unknown", joker: null };
}

export function determineWinner(hand1, hand2) {
  const a = evaluatePlayerHand(hand1);
  const b = evaluatePlayerHand(hand2);
  return {
    result: compareScores(a.score, b.score),
    name1: a.name,
    name2: b.name,
    joker1: a.joker,
    joker2: b.joker,
  };
}
