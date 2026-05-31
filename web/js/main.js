// 21 Card Poker — UI controller / main entry

import { GameEngine, Phase, Action } from "./game.js";
import { evaluatePlayerHand } from "./hand_eval.js";
import { AIPlayer } from "./ai.js";
import { sound } from "./sound.js";

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let engine = new GameEngine(1, 50);
let ai = new AIPlayer("medium");
let difficulty = "medium";
let startingChips = 50;

let selectedDiscards = new Set();
let drawPlayer = null; // which player is currently choosing to discard (only relevant for human)
let isInRaise = false;
let modalResolver = null;

// ── Rendering ────────────────────────────────────────────────────

function suitClass(card) {
  if (card.isJoker) return "joker";
  return card.color === "red" ? "red" : "black";
}

function cardEl(card, { faceDown = false, clickable = false, idx = -1, animateDeal = false } = {}) {
  const el = document.createElement("div");
  el.className = "card";
  if (animateDeal) el.classList.add("dealt");
  if (faceDown) {
    el.classList.add("back");
    return el;
  }
  el.classList.add(suitClass(card));
  if (card.isJoker) {
    el.innerHTML = `
      <div class="rank-tl">JOKER</div>
      <div class="suit-tl">★</div>
      <div class="center-suit">🃏</div>
      <div class="rank-br">JOKER</div>`;
  } else {
    el.innerHTML = `
      <div class="rank-tl">${card.rank}</div>
      <div class="suit-tl">${card.suit}</div>
      <div class="center-suit">${card.suit}</div>
      <div class="rank-br">${card.rank}</div>`;
  }
  if (clickable) {
    el.classList.add("is-clickable");
    el.dataset.idx = String(idx);
    el.addEventListener("click", () => toggleDiscard(idx, el));
  }
  return el;
}

function miniCardEl(card) {
  const el = document.createElement("div");
  el.className = "mini-card " + suitClass(card);
  el.textContent = card.isJoker ? "🃏" : `${card.rank}${card.suit}`;
  return el;
}

function render() {
  const s = engine.state;
  if (!s) return;

  $("my-chips").textContent = s.player1.chips;
  $("opp-chips").textContent = s.player2.chips;
  $("my-bet").textContent = `${s.player1.currentBet}b`;
  $("opp-bet").textContent = `${s.player2.currentBet}b`;
  $("pot").textContent = s.pot;
  $("round-num").textContent = s.roundNumber;

  $("my-role").textContent = s.starter === s.player1 ? "S" : "F";
  $("opp-role").textContent = s.starter === s.player2 ? "S" : "F";

  // Player hand
  const myHand = $("my-hand");
  const oppHand = $("opp-hand");
  const isDrawPhaseForMe =
    s.phase === Phase.DRAW &&
    ((s.drawSubPhase === "follower_draw" && s.follower === s.player1) ||
      (s.drawSubPhase === "starter_draw" && s.starter === s.player1));

  myHand.innerHTML = "";
  s.player1.hand.forEach((c, i) => {
    const el = cardEl(c, { clickable: isDrawPhaseForMe, idx: i });
    if (selectedDiscards.has(i)) el.classList.add("selected");
    myHand.appendChild(el);
  });

  // Opponent hand: face down unless showdown
  oppHand.innerHTML = "";
  const showOpp = s.phase === Phase.SHOWDOWN || s.phase === Phase.ROUND_OVER;
  s.player2.hand.forEach((c) => {
    oppHand.appendChild(cardEl(c, { faceDown: !showOpp }));
  });

  if (isDrawPhaseForMe) {
    $("discard-controls").hidden = false;
    $("discard-count").textContent = String(selectedDiscards.size);
    const myRole = s.follower === s.player1 ? "Follower" : "Starter";
    $("discard-hint").textContent = `${myRole}: tap any cards you want to discard.`;
  } else {
    $("discard-controls").hidden = true;
  }
}

function setStatus(msg) {
  $("status-msg").textContent = msg;
}

function pushLog(msg) {
  const log = $("log");
  const entry = document.createElement("div");
  entry.className = "entry";
  entry.textContent = msg;
  log.prepend(entry);
  while (log.childElementCount > 30) log.removeChild(log.lastChild);
}

// ── Discard handling ─────────────────────────────────────────────

function toggleDiscard(idx, el) {
  if (selectedDiscards.has(idx)) {
    selectedDiscards.delete(idx);
    el.classList.remove("selected");
  } else {
    selectedDiscards.add(idx);
    el.classList.add("selected");
  }
  $("discard-count").textContent = String(selectedDiscards.size);
}

// ── Action buttons ───────────────────────────────────────────────

function renderActions() {
  const s = engine.state;
  const bar = $("actions");
  bar.innerHTML = "";
  $("raise-controls").hidden = true;
  isInRaise = false;

  if (!s) return;

  // No actions during draw or terminal phases
  if (
    s.phase === Phase.DRAW ||
    s.phase === Phase.SHOWDOWN ||
    s.phase === Phase.ROUND_OVER ||
    s.phase === Phase.GAME_OVER
  ) {
    return;
  }

  if (s.currentActor !== s.player1) return;

  const avail = engine.getAvailableActions();
  for (const act of avail) {
    const btn = document.createElement("button");
    btn.className = "action-btn";
    btn.dataset.act = act;
    btn.textContent = labelFor(act);
    btn.addEventListener("click", () => onPlayerAction(act));
    bar.appendChild(btn);
  }
}

function labelFor(act) {
  if (act === Action.CALL) {
    const s = engine.state;
    const diff = s.betToMatch - s.player1.currentBet;
    return `Call (${diff}b)`;
  }
  return act;
}

function showRaiseControls() {
  isInRaise = true;
  const max = engine.getMaxRaise();
  const slider = $("raise-slider");
  slider.min = 1;
  slider.max = max;
  slider.value = Math.min(slider.value || 1, max);
  $("raise-value").textContent = slider.value;
  $("raise-controls").hidden = false;
  $("actions").innerHTML = "";
}

$("raise-slider").addEventListener("input", (e) => {
  $("raise-value").textContent = e.target.value;
});
$("confirm-raise").addEventListener("click", () => {
  const amt = parseInt($("raise-slider").value, 10);
  doAction(Action.RAISE, amt);
});
$("cancel-raise").addEventListener("click", () => {
  isInRaise = false;
  renderActions();
});

async function onPlayerAction(act) {
  if (act === Action.RAISE) {
    showRaiseControls();
    return;
  }
  doAction(act, 0);
}

async function doAction(act, raiseAmt) {
  const msg = engine.applyAction(act, raiseAmt);
  // SFX
  if (act === Action.FOLD) sound.fold();
  else if (act === Action.CHECK) sound.check();
  else if (act === Action.CALL) sound.call();
  else if (act === Action.RAISE) sound.raise();
  pushLog(msg);
  setStatus(msg);
  render();
  await sleep(300);
  await advanceTurn();
}

// Confirm discard
$("confirm-discard").addEventListener("click", async () => {
  const s = engine.state;
  const discardArr = [...selectedDiscards];
  const count = engine.doDraw(s.player1, discardArr);
  if (s.drawSubPhase === "follower_draw") s.followerDiscarded = count;
  else s.starterDiscarded = count;
  selectedDiscards.clear();
  if (count > 0) sound.deal();
  pushLog(`You discarded ${count} card${count === 1 ? "" : "s"}.`);
  setStatus(`You discarded ${count}.`);
  render();
  await sleep(400);
  engine.advanceDraw();
  await advanceTurn();
});

// ── Turn loop ────────────────────────────────────────────────────

async function advanceTurn() {
  const s = engine.state;
  render();
  renderActions();

  // Showdown
  if (s.phase === Phase.SHOWDOWN) {
    await runShowdown();
    return;
  }

  if (s.phase === Phase.ROUND_OVER) {
    await showRoundOver();
    return;
  }

  // Draw phase
  if (s.phase === Phase.DRAW) {
    if (s.currentActor === s.player1) {
      const role = s.follower === s.player1 ? "Follower" : "Starter";
      setStatus(`Your turn to draw (${role}). Select cards to discard.`);
      return;
    } else {
      // AI draws
      const role = s.follower === s.player2 ? "Follower" : "Starter";
      setStatus(`Opponent (${role}) is drawing…`);
      await sleep(800);
      const idx = ai.chooseDiscards(s);
      const count = engine.doDraw(s.player2, idx);
      if (s.drawSubPhase === "follower_draw") s.followerDiscarded = count;
      else s.starterDiscarded = count;
      pushLog(`Opponent discarded ${count} card${count === 1 ? "" : "s"}.`);
      if (count > 0) sound.deal();
      render();
      await sleep(500);
      engine.advanceDraw();
      await advanceTurn();
      return;
    }
  }

  // Betting phases
  if (s.phase === Phase.PRE_DRAW_BET || s.phase === Phase.POST_DRAW_BET) {
    if (s.currentActor === s.player1) {
      const phaseLabel = s.phase === Phase.PRE_DRAW_BET ? "Pre-draw" : "Post-draw";
      setStatus(`${phaseLabel} betting — your move.`);
      return;
    } else {
      setStatus("Opponent is thinking…");
      await sleep(900);
      const avail = engine.getAvailableActions();
      const [act, amt] = ai.chooseAction(s, avail);
      const msg = engine.applyAction(act, amt);
      if (act === Action.FOLD) sound.fold();
      else if (act === Action.CHECK) sound.check();
      else if (act === Action.CALL) sound.call();
      else if (act === Action.RAISE) sound.raise();
      pushLog(msg);
      setStatus(msg);
      render();
      await sleep(500);
      await advanceTurn();
      return;
    }
  }
}

// ── Showdown / Round over ────────────────────────────────────────

async function runShowdown() {
  const s = engine.state;
  // Determine winner
  const me = evaluatePlayerHand(s.player1.hand);
  const opp = evaluatePlayerHand(s.player2.hand);
  let result = 0;
  if (me.score[0] !== opp.score[0]) result = me.score[0] < opp.score[0] ? 1 : -1;
  else {
    const len = Math.max(me.score.length, opp.score.length);
    for (let i = 1; i < len; i++) {
      const a = me.score[i] ?? 0;
      const b = opp.score[i] ?? 0;
      if (a !== b) { result = a > b ? 1 : -1; break; }
    }
  }

  if (result > 0) {
    s.player1.chips += s.pot;
    s.roundWinner = s.player1;
    s.winnerReason = `Best hand: ${me.name}`;
  } else if (result < 0) {
    s.player2.chips += s.pot;
    s.roundWinner = s.player2;
    s.winnerReason = `Best hand: ${opp.name}`;
  } else {
    const half = Math.floor(s.pot / 2);
    s.player1.chips += half;
    s.player2.chips += s.pot - half;
    s.roundWinner = null;
    s.winnerReason = "Tie — pot split";
  }
  s.pot = 0;
  s.phase = Phase.ROUND_OVER;

  if (result > 0) sound.win();
  else if (result < 0) sound.lose();
  else sound.tie();

  render();
  await sleep(300);
  await showShowdownModal(me, opp, result);
}

async function showShowdownModal(me, opp, result) {
  const title =
    result > 0 ? "You win the pot!" : result < 0 ? "Opponent wins the pot." : "It's a tie!";
  const titleClass =
    result > 0 ? "result-win" : result < 0 ? "result-lose" : "result-tie";

  const body = document.createElement("div");
  body.innerHTML = `
    <div class="showdown-hands">
      <div class="showdown-row">
        <span class="who">You</span>
        <span class="mini-cards" id="me-mini"></span>
        <span class="what">${me.name}</span>
      </div>
      <div class="showdown-row">
        <span class="who">Opponent</span>
        <span class="mini-cards" id="opp-mini"></span>
        <span class="what">${opp.name}</span>
      </div>
    </div>
    ${me.joker ? `<p style="text-align:center;color:var(--text-dim);font-size:13px">Your Joker → <b>${me.joker.rank}${me.joker.suit}</b></p>` : ""}
    ${opp.joker ? `<p style="text-align:center;color:var(--text-dim);font-size:13px">Opponent's Joker → <b>${opp.joker.rank}${opp.joker.suit}</b></p>` : ""}
  `;

  await showModal({
    title: `<span class="${titleClass}">${title}</span>`,
    bodyEl: body,
    primaryLabel: "Next Round",
    onAfterOpen: () => {
      const meMini = document.getElementById("me-mini");
      const oppMini = document.getElementById("opp-mini");
      const s = engine.state;
      s.player1.hand.forEach((c) => meMini.appendChild(miniCardEl(c)));
      s.player2.hand.forEach((c) => oppMini.appendChild(miniCardEl(c)));
    },
  });

  await afterRound();
}

async function showRoundOver() {
  const s = engine.state;
  const win = s.roundWinner;
  const titleClass =
    win === s.player1 ? "result-win" : win === s.player2 ? "result-lose" : "result-tie";
  const title =
    win === s.player1 ? "You won the pot." : win === s.player2 ? "Opponent won the pot." : "Pot split.";

  if (win === s.player1) sound.win();
  else if (win === s.player2) sound.lose();
  else sound.tie();

  const body = document.createElement("div");
  body.innerHTML = `<p style="text-align:center">${s.winnerReason}</p>`;

  await showModal({
    title: `<span class="${titleClass}">${title}</span>`,
    bodyEl: body,
    primaryLabel: "Next Round",
  });

  await afterRound();
}

async function afterRound() {
  const winner = engine.checkGameOver();
  if (winner) {
    const isYou = winner === engine.state.player1;
    const body = document.createElement("div");
    body.innerHTML = `<p style="text-align:center;font-size:16px">${
      isYou ? "🎉 You won the match!" : "Opponent won the match."
    }</p>
    <p style="text-align:center;color:var(--text-dim)">Final chips — You: <b>${engine.state.player1.chips}</b> · Opponent: <b>${engine.state.player2.chips}</b></p>`;
    await showModal({
      title: `<span class="${isYou ? "result-win" : "result-lose"}">Game Over</span>`,
      bodyEl: body,
      primaryLabel: "Play Again",
    });
    startNewGame();
    return;
  }

  engine.swapRoles();
  engine.startRound();
  render();
  await advanceTurn();
}

// ── Modal ────────────────────────────────────────────────────────

function showModal({ title, bodyEl, primaryLabel = "Continue", onAfterOpen }) {
  return new Promise((resolve) => {
    $("modal-title").innerHTML = title;
    const body = $("modal-body");
    body.innerHTML = "";
    if (bodyEl) body.appendChild(bodyEl);
    $("modal-primary").textContent = primaryLabel;
    $("modal").classList.remove("hidden");
    if (onAfterOpen) onAfterOpen();
    modalResolver = () => {
      $("modal").classList.add("hidden");
      modalResolver = null;
      resolve();
    };
  });
}
$("modal-primary").addEventListener("click", () => modalResolver && modalResolver());

// Rules modal
$("rules-btn").addEventListener("click", () => $("rules-modal").classList.remove("hidden"));
$("rules-close").addEventListener("click", () => $("rules-modal").classList.add("hidden"));

// New game
function startNewGame() {
  engine = new GameEngine(1, startingChips);
  ai = new AIPlayer(difficulty);
  engine.newGame();
  engine.startRound();
  selectedDiscards.clear();
  render();
  setStatus("New game — pre-draw betting begins.");
  pushLog(`Round 1 dealt. ${engine.state.starter.name} posts 2b, ${engine.state.follower.name} posts 1b.`);
  sound.deal();
  advanceTurn();
}
$("new-game-btn").addEventListener("click", () => {
  sound.click();
  startNewGame();
});

// ── Main screen / settings ───────────────────────────────────────

function bindSegmented(rootId, onChange) {
  const root = $(rootId);
  root.querySelectorAll(".seg-btn").forEach((b) => {
    b.addEventListener("click", () => {
      root.querySelectorAll(".seg-btn").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      sound.click();
      onChange(b.dataset.val);
    });
  });
}

function applyDifficultyBadge() {
  const badge = $("diff-badge");
  if (!badge) return;
  badge.textContent = difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
}

function updateSoundIcon() {
  const btn = $("sound-btn");
  if (!btn) return;
  btn.textContent = sound.enabled ? "🔊" : "🔇";
  const cb = $("sound-toggle");
  if (cb) cb.checked = sound.enabled;
}

function showMainScreen() {
  $("main-screen").classList.remove("hidden");
  $("app-root").classList.add("hidden");
}
function hideMainScreen() {
  $("main-screen").classList.add("hidden");
  $("app-root").classList.remove("hidden");
}

bindSegmented("difficulty-seg", (val) => {
  difficulty = val;
  applyDifficultyBadge();
  try { localStorage.setItem("poker.difficulty", val); } catch {}
});
bindSegmented("chips-seg", (val) => {
  startingChips = parseInt(val, 10);
  try { localStorage.setItem("poker.chips", val); } catch {}
});

$("sound-toggle").addEventListener("change", (e) => {
  sound.setEnabled(e.target.checked);
  if (sound.enabled) sound.click();
  updateSoundIcon();
});
$("sound-btn").addEventListener("click", () => {
  sound.setEnabled(!sound.enabled);
  if (sound.enabled) sound.click();
  updateSoundIcon();
});

$("start-btn").addEventListener("click", () => {
  sound.resume();
  sound.start();
  hideMainScreen();
  applyDifficultyBadge();
  startNewGame();
});

$("menu-btn").addEventListener("click", () => {
  sound.click();
  showMainScreen();
});

$("hero-rules-btn").addEventListener("click", () => {
  sound.click();
  $("rules-modal").classList.remove("hidden");
});

// Restore prefs
(function restorePrefs() {
  try {
    const d = localStorage.getItem("poker.difficulty");
    if (d) {
      difficulty = d;
      const root = $("difficulty-seg");
      root.querySelectorAll(".seg-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.val === d);
      });
    }
    const c = localStorage.getItem("poker.chips");
    if (c) {
      startingChips = parseInt(c, 10);
      const root = $("chips-seg");
      root.querySelectorAll(".seg-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.val === c);
      });
    }
  } catch {}
  sound.loadPref();
  updateSoundIcon();
  applyDifficultyBadge();
})();

// Boot: show main screen, do not auto-start
showMainScreen();
