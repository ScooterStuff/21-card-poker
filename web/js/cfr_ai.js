// 21 Card Poker — CFR-trained AI ("Expert" difficulty)
//
// Loads a compact strategy JSON produced by the cardpoker-cfr trainer
// (https://github.com/ScooterStuff/21-card-poker-cfr) and uses it to choose
// betting and discard actions.
//
// The CFR strategy is keyed by an "infoset class" string of the form:
//   P1|ph=<phase>|h=<cat>.<r1>.<r2>.J<j>|opd=<oppDiscard>|bet=<betToMatch>|r=<raisesThisStreet>
//
// We construct that key live from the engine state, look it up, and pick the
// argmax action (or sample, if you prefer). Unknown infosets fall back to a
// sensible heuristic so the AI is still playable on out-of-distribution states.

import { Action, RANK_VALUES } from "./game.js";
import {
  evaluatePlayerHand,
  PAIR,
  TWO_PAIR,
  THREE_OF_A_KIND,
  STRAIGHT,
  FOUR_OF_A_KIND,
} from "./hand_eval.js";

// Action labels in the CFR action alphabet.
const A_FOLD = "F";
const A_CHECK_CALL = "C";
const A_RAISE_MIN = "Rmin";
const A_RAISE_POT = "Rpot";
const A_RAISE_ALLIN = "Rallin";
const RAISE_LABELS = new Set([A_RAISE_MIN, A_RAISE_POT, A_RAISE_ALLIN]);

const PRETTY = {
  [A_FOLD]: "Fold",
  [A_CHECK_CALL]: "Check/Call",
  [A_RAISE_MIN]: "Raise (min)",
  [A_RAISE_POT]: "Raise (pot)",
  [A_RAISE_ALLIN]: "All-in",
  D0: "Discard 0",
  D1: "Discard 1",
  D2: "Discard 2",
  D3: "Discard 3",
  D4: "Discard 4",
  D5: "Discard 5",
};

// ── Hand bucketing (must match Python `abstraction.hand_bucket`) ─────────────

export function handBucket(hand) {
  const { score } = evaluatePlayerHand(hand);
  const cat = score[0];
  const primary = score[1] ?? 0;
  const secondary = score[2] ?? 0;
  const hasJoker = hand.some((c) => c.isJoker) ? 1 : 0;
  return { cat, primary, secondary, hasJoker };
}

function bucketStr(b) {
  return `${b.cat}.${b.primary}.${b.secondary}.J${b.hasJoker}`;
}

// ── Discard heuristic (must match Python `choose_discard_indices`) ───────────

export function chooseDiscardIndices(hand, count) {
  if (count <= 0) return [];

  const groups = new Map(); // rank -> indices
  const jokerIdxs = [];
  hand.forEach((c, i) => {
    if (c.isJoker) {
      jokerIdxs.push(i);
    } else {
      if (!groups.has(c.rank)) groups.set(c.rank, []);
      groups.get(c.rank).push(i);
    }
  });

  const offGroup = [];
  const inGroup = [];
  for (const [, idxs] of groups) {
    if (idxs.length === 1) offGroup.push(idxs[0]);
    else inGroup.push(...idxs);
  }
  offGroup.sort((a, b) => (RANK_VALUES[hand[a].rank] ?? 0) - (RANK_VALUES[hand[b].rank] ?? 0));

  const chosen = offGroup.slice(0, count);
  if (chosen.length >= count) return chosen.slice().sort((a, b) => a - b);

  inGroup.sort((a, b) => (RANK_VALUES[hand[a].rank] ?? 0) - (RANK_VALUES[hand[b].rank] ?? 0));
  chosen.push(...inGroup.slice(0, count - chosen.length));
  return chosen.slice().sort((a, b) => a - b);
}

// ── Strategy loader ──────────────────────────────────────────────────────────

let _strategyPromise = null;
let _strategyCache = null;

export function loadStrategy(url = "data/cfr_strategy.json") {
  if (_strategyCache) return Promise.resolve(_strategyCache);
  if (_strategyPromise) return _strategyPromise;
  _strategyPromise = fetch(url, { cache: "force-cache" })
    .then((r) => {
      if (!r.ok) throw new Error(`failed to load CFR strategy: HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      _strategyCache = data;
      return data;
    });
  return _strategyPromise;
}

// ── Live infoset key construction ────────────────────────────────────────────

function bettingPhaseTag(state) {
  // Match the Python phase tags: "pre" | "post".
  // engine state phases are PRE_DRAW_BET / POST_DRAW_BET — see game.js
  if (state.phase === "PRE_DRAW_BET") return "pre";
  if (state.phase === "POST_DRAW_BET") return "post";
  return null;
}

function buildBettingKey(state, actor, raisesThisStreet) {
  const ph = bettingPhaseTag(state);
  if (!ph) return null;
  const b = handBucket(actor.hand);
  // Opponent's discard count (only set after draw phase ends).
  let oppDisc;
  if (actor === state.starter) oppDisc = state.followerDiscarded;
  else oppDisc = state.starterDiscarded;
  // Bet outstanding from the actor's perspective.
  const betToMatch = Math.max(state.betToMatch - actor.currentBet, 0);
  // P1 in the trained game = whichever player is to act. (CFR keyed on `to_act`.)
  // Phase semantics: pre-draw F acts first → tag P1 (follower) for pre, etc.
  // But our trained strategy was symmetric over players via separate P0/P1 keys
  // for the actor each turn. The engine here doesn't distinguish — we just
  // ask "what would the trained player at this position do" and key on actor
  // role within the round.
  const playerTag = actor === state.starter ? "P0" : "P1";
  return `${playerTag}|ph=${ph}|h=${bucketStr(b)}|opd=${oppDisc}|bet=${betToMatch}|r=${raisesThisStreet}`;
}

function buildDrawKey(state, actor) {
  const subToPhase = {
    follower_draw: "drF",
    starter_draw: "drS",
  };
  const ph = subToPhase[state.drawSubPhase];
  if (!ph) return null;
  const b = handBucket(actor.hand);
  const oppDisc = actor === state.starter ? state.followerDiscarded : state.starterDiscarded;
  const playerTag = actor === state.starter ? "P0" : "P1";
  // bet/r are 0 inside draw nodes per the trained game tree.
  return `${playerTag}|ph=${ph}|h=${bucketStr(b)}|opd=${oppDisc}|bet=0|r=0`;
}

// ── Strategy lookup with fallbacks ───────────────────────────────────────────

function lookupStrategy(table, key) {
  const entry = table.infosets ? table.infosets[key] : null;
  return entry || null;
}

// Among legal labels, pick by argmax of the trained probabilities (with mass
// re-normalised over only the legal subset). Returns { action, probs, pretty }.
function pickFromTable(legalLabels, entry, rng) {
  if (!entry) {
    // Uniform over legal as a fallback.
    const n = legalLabels.length || 1;
    const probs = legalLabels.map(() => 1 / n);
    return {
      action: legalLabels[Math.floor(rng() * n)],
      probs,
      labels: legalLabels.slice(),
      source: "uniform-fallback",
    };
  }
  const pairs = [];
  for (let i = 0; i < entry.actions.length; i++) {
    const a = entry.actions[i];
    if (legalLabels.includes(a)) pairs.push([a, entry.probs[i] || 0]);
  }
  if (pairs.length === 0) {
    const n = legalLabels.length || 1;
    return {
      action: legalLabels[Math.floor(rng() * n)],
      probs: legalLabels.map(() => 1 / n),
      labels: legalLabels.slice(),
      source: "no-overlap-fallback",
    };
  }
  const total = pairs.reduce((s, [, p]) => s + p, 0) || 1;
  const labels = pairs.map(([a]) => a);
  const probs = pairs.map(([, p]) => p / total);
  // Argmax (deterministic). Switch to sampling if you'd rather randomise.
  let bestIdx = 0;
  for (let i = 1; i < probs.length; i++) if (probs[i] > probs[bestIdx]) bestIdx = i;
  return {
    action: labels[bestIdx],
    probs,
    labels,
    source: "cfr",
  };
}

// ── Public AI class ──────────────────────────────────────────────────────────

export class CFRAIPlayer {
  constructor() {
    this.difficulty = "expert";
    this.strategy = null;     // populated once loaded
    this.lastDecision = null; // { kind, key, labels, probs, picked, source }
    this._raisesThisStreet = 0;
    this._lastPhase = null;
    this._rng = Math.random;
  }

  async ready(url) {
    this.strategy = await loadStrategy(url);
    return this;
  }

  // Track raises-per-street locally so we can build infoset keys without
  // modifying the engine. Call from main.js BEFORE every AI turn.
  observeStateForKey(state) {
    if (state.phase !== this._lastPhase) {
      this._raisesThisStreet = 0;
      this._lastPhase = state.phase;
    }
  }

  noteRaiseHappened() {
    this._raisesThisStreet += 1;
  }

  // ── Betting decision ───────────────────────────────────────────────────────

  chooseAction(state, available) {
    const ai = state.player2;
    const opp = state.player1;
    this.observeStateForKey(state);

    const diff = Math.max(state.betToMatch - ai.currentBet, 0);
    const maxRaise = Math.max(Math.min(ai.chips - diff, opp.chips), 1);

    // Build the legal CFR-action set from the engine's available list.
    const legalLabels = [];
    if (available.includes(Action.FOLD)) legalLabels.push(A_FOLD);
    if (available.includes(Action.CHECK) || available.includes(Action.CALL)) {
      legalLabels.push(A_CHECK_CALL);
    }
    if (available.includes(Action.RAISE)) {
      legalLabels.push(A_RAISE_MIN);
      const potAmt = Math.max(1, state.pot);
      if (potAmt > 1 && potAmt < maxRaise) legalLabels.push(A_RAISE_POT);
      if (maxRaise > 1) legalLabels.push(A_RAISE_ALLIN);
    }

    let key = null;
    let entry = null;
    if (this.strategy) {
      key = buildBettingKey(state, ai, this._raisesThisStreet);
      if (key) entry = lookupStrategy(this.strategy, key);
    }

    const pick = pickFromTable(legalLabels, entry, this._rng);
    this.lastDecision = {
      kind: "bet",
      phase: state.phase,
      key,
      labels: pick.labels,
      probs: pick.probs,
      picked: pick.action,
      pretty: pick.labels.map((a) => PRETTY[a] || a),
      source: pick.source,
      handBucket: handBucket(ai.hand),
    };

    if (RAISE_LABELS.has(pick.action)) this.noteRaiseHappened();

    return translateBetAction(pick.action, state, ai, opp, maxRaise);
  }

  // ── Discard decision ───────────────────────────────────────────────────────

  chooseDiscards(state) {
    const ai = state.player2;
    const legalLabels = [];
    for (let n = 0; n <= 5; n++) legalLabels.push(`D${n}`);

    let key = null;
    let entry = null;
    if (this.strategy) {
      key = buildDrawKey(state, ai);
      if (key) entry = lookupStrategy(this.strategy, key);
    }

    const pick = pickFromTable(legalLabels, entry, this._rng);
    const count = parseInt(pick.action.slice(1), 10);

    this.lastDecision = {
      kind: "draw",
      phase: state.phase,
      key,
      labels: pick.labels,
      probs: pick.probs,
      picked: pick.action,
      pretty: pick.labels.map((a) => PRETTY[a] || a),
      source: pick.source,
      handBucket: handBucket(ai.hand),
      count,
    };

    return chooseDiscardIndices(ai.hand, count);
  }
}

function translateBetAction(label, state, ai, opp, maxRaise) {
  if (label === A_FOLD) return [Action.FOLD, 0];
  if (label === A_CHECK_CALL) {
    const diff = state.betToMatch - ai.currentBet;
    return diff > 0 ? [Action.CALL, 0] : [Action.CHECK, 0];
  }
  let amt = 1;
  if (label === A_RAISE_MIN) amt = 1;
  else if (label === A_RAISE_POT) amt = Math.max(1, state.pot);
  else if (label === A_RAISE_ALLIN) amt = maxRaise;
  amt = Math.max(1, Math.min(amt, maxRaise));
  return [Action.RAISE, amt];
}

// ── Position-agnostic advice (used for the human player) ─────────────────────
//
// Returns null until the strategy has been loaded. `getDiscardAdvice` returns
// both the recommended count and the concrete card indices (using the same
// heuristic the AI uses, so the advice stays consistent with how the strategy
// was trained).

export function getBetAdvice(state, player, raisesThisStreet, available, strategyTable) {
  if (!strategyTable) return null;
  const opp = player === state.player1 ? state.player2 : state.player1;
  const diff = Math.max(state.betToMatch - player.currentBet, 0);
  const maxRaise = Math.max(Math.min(player.chips - diff, opp.chips), 1);

  const legalLabels = [];
  if (available.includes(Action.FOLD)) legalLabels.push(A_FOLD);
  if (available.includes(Action.CHECK) || available.includes(Action.CALL)) {
    legalLabels.push(A_CHECK_CALL);
  }
  if (available.includes(Action.RAISE)) {
    legalLabels.push(A_RAISE_MIN);
    const potAmt = Math.max(1, state.pot);
    if (potAmt > 1 && potAmt < maxRaise) legalLabels.push(A_RAISE_POT);
    if (maxRaise > 1) legalLabels.push(A_RAISE_ALLIN);
  }

  const key = buildBettingKey(state, player, raisesThisStreet);
  const entry = key ? lookupStrategy(strategyTable, key) : null;
  const pick = pickFromTable(legalLabels, entry, Math.random);
  return {
    key,
    labels: pick.labels,
    pretty: pick.labels.map((a) => PRETTY[a] || a),
    probs: pick.probs,
    picked: pick.action,
    pickedPretty: PRETTY[pick.action] || pick.action,
    source: pick.source,
  };
}

export function getDiscardAdvice(state, player, strategyTable) {
  const legalLabels = [];
  for (let n = 0; n <= 5; n++) legalLabels.push(`D${n}`);

  if (!strategyTable) {
    // Heuristic-only fallback: keep groups + joker, drop two lowest off-group cards.
    const indices = chooseDiscardIndices(player.hand, 2);
    return {
      key: null,
      labels: legalLabels,
      pretty: legalLabels.map((a) => PRETTY[a]),
      probs: legalLabels.map((a) => (a === "D2" ? 1 : 0)),
      picked: "D2",
      pickedPretty: "Discard 2",
      source: "heuristic",
      count: indices.length,
      indices,
    };
  }

  const key = buildDrawKey(state, player);
  const entry = key ? lookupStrategy(strategyTable, key) : null;
  const pick = pickFromTable(legalLabels, entry, Math.random);
  const count = parseInt(pick.action.slice(1), 10);
  const indices = chooseDiscardIndices(player.hand, count);
  return {
    key,
    labels: pick.labels,
    pretty: pick.labels.map((a) => PRETTY[a] || a),
    probs: pick.probs,
    picked: pick.action,
    pickedPretty: PRETTY[pick.action] || pick.action,
    source: pick.source,
    count,
    indices,
  };
}
