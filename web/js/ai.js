// 21 Card Poker — AI opponent

import { Action } from "./game.js";
import {
  evaluatePlayerHand,
  STRAIGHT,
  THREE_OF_A_KIND,
  TWO_PAIR,
  PAIR,
  FOUR_OF_A_KIND,
} from "./hand_eval.js";

const rand = () => Math.random();
const randInt = (lo, hi) => Math.floor(rand() * (hi - lo + 1)) + lo;

export class AIPlayer {
  chooseAction(state, available) {
    const ai = state.player2;
    const opp = state.player1;
    const { score } = evaluatePlayerHand(ai.hand);
    const handRank = score[0];

    const diff = Math.max(state.betToMatch - ai.currentBet, 0);
    const maxRaise = Math.max(Math.min(ai.chips - diff, opp.chips), 1);

    const pickRaise = (lo, hi) => {
      const a = Math.max(1, Math.floor(maxRaise * lo));
      const b = Math.max(a, Math.floor(maxRaise * hi));
      return randInt(a, b);
    };

    if (handRank <= FOUR_OF_A_KIND) {
      if (available.includes(Action.RAISE)) return [Action.RAISE, pickRaise(0.5, 1.0)];
      if (available.includes(Action.CALL)) return [Action.CALL, 0];
      if (available.includes(Action.CHECK)) return [Action.CHECK, 0];
    } else if (handRank <= STRAIGHT) {
      if (available.includes(Action.RAISE) && rand() < 0.65)
        return [Action.RAISE, pickRaise(0.25, 0.6)];
      if (available.includes(Action.CALL)) return [Action.CALL, 0];
      if (available.includes(Action.CHECK)) return [Action.CHECK, 0];
    } else if (handRank === THREE_OF_A_KIND) {
      if (available.includes(Action.RAISE) && rand() < 0.3)
        return [Action.RAISE, pickRaise(0.1, 0.35)];
      if (available.includes(Action.CALL)) return [Action.CALL, 0];
      if (available.includes(Action.CHECK)) return [Action.CHECK, 0];
    } else if (handRank === TWO_PAIR) {
      if (available.includes(Action.CALL)) return [Action.CALL, 0];
      if (available.includes(Action.CHECK)) return [Action.CHECK, 0];
      if (available.includes(Action.RAISE) && rand() < 0.15)
        return [Action.RAISE, pickRaise(0.05, 0.15)];
    } else {
      if (available.includes(Action.CHECK)) return [Action.CHECK, 0];
      if (available.includes(Action.CALL)) {
        const cost = state.betToMatch - ai.currentBet;
        if (cost <= 1 || rand() < 0.5) return [Action.CALL, 0];
        return [Action.FOLD, 0];
      }
      if (available.includes(Action.RAISE) && rand() < 0.1)
        return [Action.RAISE, pickRaise(0.05, 0.15)];
    }

    if (available.includes(Action.CHECK)) return [Action.CHECK, 0];
    if (available.includes(Action.CALL)) return [Action.CALL, 0];
    return [Action.FOLD, 0];
  }

  chooseDiscards(state) {
    const ai = state.player2;
    const hand = ai.hand;
    const { score } = evaluatePlayerHand(hand);
    const handRank = score[0];

    if (handRank <= STRAIGHT) return [];

    const groups = {};
    hand.forEach((c, i) => {
      const r = c.isJoker ? "Joker" : c.rank;
      (groups[r] = groups[r] || []).push(i);
    });

    const keep = new Set();
    if (groups["Joker"]) groups["Joker"].forEach((i) => keep.add(i));
    for (const [r, idxs] of Object.entries(groups)) {
      if (r === "Joker") continue;
      if (idxs.length >= 2) idxs.forEach((i) => keep.add(i));
    }

    if (handRank === THREE_OF_A_KIND || handRank === TWO_PAIR) {
      return [0, 1, 2, 3, 4].filter((i) => !keep.has(i));
    }

    if (handRank === PAIR) {
      let discard = [0, 1, 2, 3, 4].filter((i) => !keep.has(i));
      if (discard.length > 3) {
        const sorted = discard
          .map((i) => ({ i, v: hand[i].value }))
          .sort((a, b) => b.v - a.v);
        const keepExtra = sorted[0].i;
        discard = discard.filter((i) => i !== keepExtra);
      }
      return discard;
    }

    const indexed = [];
    for (let i = 0; i < 5; i++) if (!hand[i].isJoker) indexed.push({ i, v: hand[i].value });
    indexed.sort((a, b) => a.v - b.v);
    return indexed.slice(0, 2).map((x) => x.i);
  }
}
