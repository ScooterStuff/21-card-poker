// 21 Card Poker — Core game logic (deck, dealing, betting, round flow)

export const RANKS = ["A", "K", "Q", "J", "10"];
export const SUITS = ["♠", "♥", "♦", "♣"];
export const RANK_VALUES = { A: 5, K: 4, Q: 3, J: 2, "10": 1 };
export const SUIT_COLORS = { "♠": "black", "♣": "black", "♥": "red", "♦": "red" };

export const Phase = Object.freeze({
  FORCED_BETS: "FORCED_BETS",
  PRE_DRAW_BET: "PRE_DRAW_BET",
  DRAW: "DRAW",
  POST_DRAW_BET: "POST_DRAW_BET",
  SHOWDOWN: "SHOWDOWN",
  ROUND_OVER: "ROUND_OVER",
  GAME_OVER: "GAME_OVER",
});

export const Action = Object.freeze({
  FOLD: "Fold",
  CHECK: "Check",
  CALL: "Call",
  RAISE: "Raise",
});

export class Card {
  constructor(rank, suit, isJoker = false) {
    this.rank = rank;
    this.suit = suit;
    this.isJoker = isJoker;
  }
  get value() {
    return this.isJoker ? 100 : RANK_VALUES[this.rank] ?? 0;
  }
  get color() {
    if (this.isJoker) return "purple";
    return SUIT_COLORS[this.suit] ?? "black";
  }
  toString() {
    return this.isJoker ? "🃏" : `${this.rank}${this.suit}`;
  }
}

export const JOKER = new Card("Joker", "", true);

export function makeDeck() {
  const cards = [];
  for (const r of RANKS) for (const s of SUITS) cards.push(new Card(r, s));
  cards.push(new Card("Joker", "", true));
  // Fisher-Yates shuffle
  for (let i = cards.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [cards[i], cards[j]] = [cards[j], cards[i]];
  }
  return cards;
}

export class Player {
  constructor(name, chips, isHuman = true) {
    this.name = name;
    this.chips = chips;
    this.hand = [];
    this.isHuman = isHuman;
    this.currentBet = 0;
  }
  resetHand() {
    this.hand = [];
    this.currentBet = 0;
  }
}

export class GameEngine {
  constructor(baseBet = 1, startingChips = 50) {
    this.baseBet = baseBet;
    this.startingChips = startingChips;
    this.state = null;
  }

  newGame() {
    const p1 = new Player("You", this.startingChips, true);
    const p2 = new Player("Opponent", this.startingChips, false);
    this.state = {
      player1: p1,
      player2: p2,
      starter: p1,
      follower: p2,
      pot: 0,
      deck: [],
      discardPile: [],
      phase: Phase.FORCED_BETS,
      currentActor: null,
      betToMatch: 0,
      roundNumber: 0,
      roundWinner: null,
      winnerReason: "",
      lastActionText: "",
      followerDiscarded: -1,
      starterDiscarded: -1,
      drawSubPhase: "",
      jokerResolvedAs: null,
      firstActorChecked: false,
    };
    return this.state;
  }

  startRound() {
    const s = this.state;
    s.roundNumber += 1;
    s.pot = 0;
    s.roundWinner = null;
    s.winnerReason = "";
    s.lastActionText = "";
    s.followerDiscarded = -1;
    s.starterDiscarded = -1;
    s.drawSubPhase = "";
    s.firstActorChecked = false;
    s.jokerResolvedAs = null;

    s.player1.resetHand();
    s.player2.resetHand();

    const starterBet = Math.min(2 * this.baseBet, s.starter.chips);
    const followerBet = Math.min(1 * this.baseBet, s.follower.chips);

    s.starter.chips -= starterBet;
    s.starter.currentBet = starterBet;
    s.follower.chips -= followerBet;
    s.follower.currentBet = followerBet;
    s.pot = starterBet + followerBet;
    s.betToMatch = starterBet;

    s.deck = makeDeck();
    for (let i = 0; i < 5; i++) {
      s.player1.hand.push(s.deck.pop());
      s.player2.hand.push(s.deck.pop());
    }
    s.player1.hand.sort((a, b) => b.value - a.value);
    s.player2.hand.sort((a, b) => b.value - a.value);
    s.discardPile = [];

    s.phase = Phase.PRE_DRAW_BET;
    s.currentActor = s.follower;
  }

  getAvailableActions() {
    const s = this.state;
    const actor = s.currentActor;
    const opponent = actor === s.player2 ? s.player1 : s.player2;
    const actions = [];

    if (s.phase === Phase.PRE_DRAW_BET) {
      const diff = s.betToMatch - actor.currentBet;
      if (diff > 0) actions.push(Action.CALL);
      if (actor.chips > Math.max(diff, 0) && opponent.chips > 0) actions.push(Action.RAISE);
      actions.push(Action.FOLD);
    } else if (s.phase === Phase.POST_DRAW_BET) {
      const diff = s.betToMatch - actor.currentBet;
      if (diff === 0) actions.push(Action.CHECK);
      if (diff > 0) actions.push(Action.CALL);
      if (actor.chips > Math.max(diff, 0) && opponent.chips > 0) actions.push(Action.RAISE);
      actions.push(Action.FOLD);
    }
    return actions;
  }

  getMaxRaise() {
    const s = this.state;
    const actor = s.currentActor;
    const opponent = actor === s.player2 ? s.player1 : s.player2;
    const diff = Math.max(s.betToMatch - actor.currentBet, 0);
    const actorCanAdd = actor.chips - diff;
    return Math.max(Math.min(actorCanAdd, opponent.chips), 1);
  }

  applyAction(action, raiseAmount = 1) {
    const s = this.state;
    const actor = s.currentActor;
    const opponent = actor === s.player2 ? s.player1 : s.player2;

    if (action === Action.FOLD) {
      s.roundWinner = opponent;
      s.winnerReason = `${actor.name} folded`;
      s.phase = Phase.ROUND_OVER;
      opponent.chips += s.pot;
      s.pot = 0;
      return `${actor.name} folds!`;
    }

    if (action === Action.CHECK) {
      const msg = `${actor.name} checks.`;
      if (s.firstActorChecked) {
        s.phase = Phase.SHOWDOWN;
      } else {
        s.firstActorChecked = true;
        s.currentActor = opponent;
      }
      return msg;
    }

    if (action === Action.CALL) {
      const diff = s.betToMatch - actor.currentBet;
      const actual = Math.min(diff, actor.chips);
      actor.chips -= actual;
      actor.currentBet += actual;
      s.pot += actual;
      const msg = `${actor.name} calls (${actual}b).`;
      if (s.phase === Phase.PRE_DRAW_BET) {
        s.phase = Phase.DRAW;
        s.drawSubPhase = "follower_draw";
        s.currentActor = s.follower;
      } else if (s.phase === Phase.POST_DRAW_BET) {
        s.phase = Phase.SHOWDOWN;
      }
      return msg;
    }

    if (action === Action.RAISE) {
      const diff = s.betToMatch - actor.currentBet;
      const maxR = this.getMaxRaise();
      const raiseBy = Math.max(1, Math.min(raiseAmount, maxR));
      const total = diff + raiseBy;
      const actual = Math.min(total, actor.chips);
      actor.chips -= actual;
      actor.currentBet += actual;
      s.pot += actual;
      s.betToMatch = actor.currentBet;
      s.currentActor = opponent;
      return `${actor.name} raises by ${raiseBy}b (total bet: ${actor.currentBet}b)!`;
    }
    return "";
  }

  doDraw(player, discardIndices) {
    const s = this.state;
    const indices = [...discardIndices].sort((a, b) => b - a);
    const discarded = [];
    for (const idx of indices) {
      if (idx >= 0 && idx < player.hand.length) {
        discarded.push(player.hand.splice(idx, 1)[0]);
      }
    }
    s.discardPile.push(...discarded);
    const drawn = Math.min(discarded.length, s.deck.length);
    for (let i = 0; i < drawn; i++) player.hand.push(s.deck.pop());
    player.hand.sort((a, b) => b.value - a.value);
    return discarded.length;
  }

  advanceDraw() {
    const s = this.state;
    if (s.drawSubPhase === "follower_draw") {
      s.drawSubPhase = "starter_draw";
      s.currentActor = s.starter;
    } else if (s.drawSubPhase === "starter_draw") {
      s.phase = Phase.POST_DRAW_BET;
      s.currentActor = s.starter;
      s.firstActorChecked = false;
      s.player1.currentBet = 0;
      s.player2.currentBet = 0;
      s.betToMatch = 0;
    }
  }

  swapRoles() {
    const s = this.state;
    [s.starter, s.follower] = [s.follower, s.starter];
  }

  checkGameOver() {
    const s = this.state;
    if (s.player1.chips <= 0) return s.player2;
    if (s.player2.chips <= 0) return s.player1;
    return null;
  }
}
