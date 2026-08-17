// ---- Core game logic (ported from solver.py) ----
function makeDeck() {
  const deck = [];
  for (let r = 2; r <= 14; r++) for (let s = 0; s < 4; s++) deck.push([r, s]);
  return deck;
}

function handRank(cards) {
  const ranks = cards.map(c => c[0]).sort((a, b) => b - a);
  const suits = cards.map(c => c[1]);
  const n = cards.length;
  const rankCounts = {};
  for (const r of ranks) rankCounts[r] = (rankCounts[r] || 0) + 1;
  const counts = Object.entries(rankCounts).map(([r, c]) => [+r, c])
    .sort((a, b) => (b[1] - a[1]) || (b[0] - a[0]));
  const isFlush = n === 5 && new Set(suits).size === 1;
  const uniq = [...new Set(ranks)].sort((a, b) => b - a);
  let isStraight = false, straightHigh = null;
  if (n === 5 && uniq.length === 5) {
    if (uniq[0] - uniq[4] === 4) { isStraight = true; straightHigh = uniq[0]; }
    else if (uniq.join(',') === '14,5,4,3,2') { isStraight = true; straightHigh = 5; }
  }
  if (n < 5) {
    let cat = 0;
    if (counts[0][1] === 4) cat = 7;
    else if (counts[0][1] === 3) cat = 3;
    else if (counts[0][1] === 2 && counts.length > 1 && counts[1][1] === 2) cat = 2;
    else if (counts[0][1] === 2) cat = 1;
    return [cat, counts.map(c => c[0]).concat(ranks)];
  }
  if (isStraight && isFlush) return [8, [straightHigh]];
  if (counts[0][1] === 4) {
    const kicker = Math.max(...ranks.filter(r => r !== counts[0][0]));
    return [7, [counts[0][0], kicker]];
  }
  if (counts[0][1] === 3 && counts[1][1] === 2) return [6, [counts[0][0], counts[1][0]]];
  if (isFlush) return [5, ranks];
  if (isStraight) return [4, [straightHigh]];
  if (counts[0][1] === 3) {
    const kickers = ranks.filter(r => r !== counts[0][0]).sort((a, b) => b - a);
    return [3, [counts[0][0], ...kickers]];
  }
  if (counts[0][1] === 2 && counts[1][1] === 2) {
    const pairRanks = [counts[0][0], counts[1][0]].sort((a, b) => b - a);
    const kicker = Math.max(...ranks.filter(r => !pairRanks.includes(r)));
    return [2, [...pairRanks, kicker]];
  }
  if (counts[0][1] === 2) {
    const kickers = ranks.filter(r => r !== counts[0][0]).sort((a, b) => b - a);
    return [1, [counts[0][0], ...kickers]];
  }
  return [0, ranks];
}

function cmpRank(a, b) {
  // a,b = [cat, tiebreakArr]
  if (a[0] !== b[0]) return a[0] - b[0];
  const ta = a[1], tb = b[1];
  for (let i = 0; i < Math.max(ta.length, tb.length); i++) {
    const va = ta[i] ?? -1, vb = tb[i] ?? -1;
    if (va !== vb) return va - vb;
  }
  return 0;
}

function partialStrength(cards) { return cards.length ? handRank(cards)[0] : -1; }

function fitScore(card, slotCards, rankW = 12, suitW = 1, straightW = 0.5, highW = 0.05) {
  const [r, s] = card;
  if (slotCards.length >= 5) return -999;
  const ranksIn = slotCards.map(c => c[0]);
  const suitsIn = slotCards.map(c => c[1]);
  const rc = {}; for (const x of ranksIn) rc[x] = (rc[x] || 0) + 1;
  const sc = {}; for (const x of suitsIn) sc[x] = (sc[x] || 0) + 1;
  let score = (rc[r] || 0) * rankW + (sc[s] || 0) * suitW;
  if (slotCards.length) {
    const mind = Math.min(...ranksIn.map(x => Math.abs(r - x)));
    if (mind <= 4) score += Math.max(0, 5 - mind) * straightW;
  }
  score += r * highW;
  return score;
}

function heuristicAction(hand, ownTable, oppTable, burned) {
  const openSlots = [0, 1, 2, 3].filter(i => ownTable[i].length < 5);
  if (!openSlots.length) return ['burn', hand[0]];
  const playsMade = ownTable.reduce((a, s) => a + s.length, 0);
  const empties = [0, 1, 2, 3].filter(i => ownTable[i].length === 0);
  if (playsMade < 4 && empties.length) {
    const c = hand.reduce((a, b) => (a[0] <= b[0] ? a : b));
    return ['play', c, empties[0]];
  }
  const best = new Map();
  for (const c of hand) {
    const scored = openSlots.map(i => {
      const base = fitScore(c, ownTable[i]);
      const weakBonus = -partialStrength(oppTable[i]) * 3;
      return [base + weakBonus, i];
    });
    scored.sort((a, b) => b[0] - a[0]);
    best.set(c, scored[0]);
  }
  let bestCard = hand[0], bestVal = best.get(hand[0])[0];
  for (const c of hand) if (best.get(c)[0] > bestVal) { bestCard = c; bestVal = best.get(c)[0]; }
  let worstCard = hand[0], worstVal = best.get(hand[0])[0];
  for (const c of hand) if (best.get(c)[0] < worstVal) { worstCard = c; worstVal = best.get(c)[0]; }
  if (!burned && worstVal < 1.5 && bestVal < 1.5) return ['burn', worstCard];
  return ['play', bestCard, best.get(bestCard)[1]];
}

// ---- State ----
function cloneState(s) {
  return {
    hands: [s.hands[0].map(c => c.slice()), s.hands[1].map(c => c.slice())],
    tables: [s.tables[0].map(col => col.map(c => c.slice())), s.tables[1].map(col => col.map(c => c.slice()))],
    burned: s.burned.slice(),
    deck: s.deck.map(c => c.slice()),
    toMove: s.toMove,
  };
}
function cardEq(a, b) { return a[0] === b[0] && a[1] === b[1]; }
function removeCard(arr, c) {
  const idx = arr.findIndex(x => cardEq(x, c));
  arr.splice(idx, 1);
}
function legalActions(state) {
  const p = state.toMove;
  const hand = state.hands[p];
  const openSlots = [0, 1, 2, 3].filter(i => state.tables[p][i].length < 5);
  const actions = [];
  for (const c of hand) for (const sIdx of openSlots) actions.push(['play', c, sIdx]);
  if (!state.burned[p]) for (const c of hand) actions.push(['burn', c]);
  return actions;
}
function step(state, action) {
  const s = cloneState(state);
  const p = s.toMove;
  if (action[0] === 'burn') { removeCard(s.hands[p], action[1]); s.burned[p] = true; }
  else { removeCard(s.hands[p], action[1]); s.tables[p][action[2]].push(action[1]); }
  if (s.deck.length) s.hands[p].push(s.deck.pop());
  s.toMove = 1 - p;
  return s;
}
function isTerminal(state) { return state.deck.length === 0; }
function evaluateTerminal(state, rootPlayer) {
  const wins = [0, 0];
  for (let i = 0; i < 4; i++) {
    const ra = handRank(state.tables[0][i]), rb = handRank(state.tables[1][i]);
    const c = cmpRank(ra, rb);
    if (c > 0) wins[0]++; else if (c < 0) wins[1]++;
  }
  const ra = handRank(state.hands[0]), rb = handRank(state.hands[1]);
  const c = cmpRank(ra, rb);
  if (c > 0) wins[0]++; else if (c < 0) wins[1]++;
  let result = 0;
  if (wins[0] >= 3) result = 1; else if (wins[1] >= 3) result = -1;
  return rootPlayer === 0 ? result : -result;
}
function rollout(state) {
  let s = state;
  while (!isTerminal(s)) {
    const p = s.toMove;
    const a = heuristicAction(s.hands[p], s.tables[p], s.tables[1 - p], s.burned[p]);
    s = step(s, a);
  }
  return s;
}

// ---- MCTS ----
function shuffle(arr, rng) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}
class Node {
  constructor(state, parent = null, action = null) {
    this.state = state; this.parent = parent; this.action = action;
    this.children = [];
    this.untried = isTerminal(state) ? [] : legalActions(state);
    this.visits = 0; this.value = 0;
    this.player = state.toMove;
  }
}
function uctSelect(node, rootPlayer, c = 1.4) {
  let best = null, bestScore = -Infinity;
  for (const ch of node.children) {
    if (ch.visits === 0) return ch;
    let q = ch.value / ch.visits;
    q = node.player === rootPlayer ? q : -q;
    const score = q + c * Math.sqrt(Math.log(node.visits) / ch.visits);
    if (score > bestScore) { bestScore = score; best = ch; }
  }
  return best;
}
function mctsSearch(rootState, rootPlayer, iterations, rng) {
  const root = new Node(rootState);
  shuffle(root.untried, rng);
  for (let it = 0; it < iterations; it++) {
    let node = root;
    while (!node.untried.length && node.children.length && !isTerminal(node.state)) {
      node = uctSelect(node, rootPlayer);
    }
    if (node.untried.length && !isTerminal(node.state)) {
      const a = node.untried.pop();
      const child = new Node(step(node.state, a), node, a);
      shuffle(child.untried, rng);
      node.children.push(child);
      node = child;
    }
    const terminalState = isTerminal(node.state) ? node.state : rollout(node.state);
    const result = evaluateTerminal(terminalState, rootPlayer);
    let n = node;
    while (n) { n.visits++; n.value += result; n = n.parent; }
  }
  return root.children.map(ch => ({ action: ch.action, visits: ch.visits, value: ch.value }));
}

function determinize(rootHand, rootTable, oppTable, rootBurned, rootBurnCard, oppBurned, rng) {
  const full = makeDeck();
  const knownKeys = new Set();
  const addKnown = c => knownKeys.add(c[0] + '_' + c[1]);
  rootHand.forEach(addKnown);
  rootTable.forEach(col => col.forEach(addKnown));
  oppTable.forEach(col => col.forEach(addKnown));
  if (rootBurned && rootBurnCard) addKnown(rootBurnCard);
  let unseen = full.filter(c => !knownKeys.has(c[0] + '_' + c[1]));
  shuffle(unseen, rng);
  let idx = 0;
  const oppHand = unseen.slice(idx, idx + 5); idx += 5;
  if (oppBurned) idx += 1;
  const remainingDeck = unseen.slice(idx);
  return {
    hands: [rootHand.map(c => c.slice()), oppHand],
    tables: [rootTable.map(col => col.map(c => c.slice())), oppTable.map(col => col.map(c => c.slice()))],
    burned: [rootBurned, oppBurned],
    deck: remainingDeck,
    toMove: 0,
  };
}

function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function solve(rootHand, rootTable, oppTable, rootBurned, rootBurnCard, oppBurned, timeBudgetMs, itersPerDet, seed) {
  const rng = mulberry32(seed);
  const actionStats = new Map(); // key -> {visits, value, action}
  const start = Date.now();
  let dets = 0;
  while (Date.now() - start < timeBudgetMs) {
    const det = determinize(rootHand, rootTable, oppTable, rootBurned, rootBurnCard, oppBurned, rng);
    const stats = mctsSearch(det, 0, itersPerDet, rng);
    for (const { action, visits, value } of stats) {
      const key = action[0] + '_' + action[1][0] + '_' + action[1][1] + '_' + (action[2] ?? '');
      if (!actionStats.has(key)) actionStats.set(key, { visits: 0, value: 0, action });
      const e = actionStats.get(key);
      e.visits += visits; e.value += value;
    }
    dets++;
  }
  const ranked = [...actionStats.values()].map(e => ({
    action: e.action, winRate: e.visits > 0 ? (e.value / e.visits + 1) / 2 : 0.5, visits: e.visits,
  }));
  ranked.sort((a, b) => b.winRate - a.winRate);
  return { ranked, dets, elapsed: (Date.now() - start) / 1000 };
}

// ---- Test ----
const rootHand = [[7, 0], [11, 0], [10, 3], [9, 0], [5, 0]];
const rootTable = [
  [[2, 3], [13, 3], [14, 3], [14, 0], [12, 3]],
  [[4, 1]],
  [[5, 1], [8, 1], [8, 2], [5, 3], [12, 1]],
  [[3, 1]],
];
const oppTable = [
  [[3, 0]],
  [[3, 2], [3, 3], [13, 2], [12, 2]],
  [[2, 2], [2, 1]],
  [[7, 3], [8, 3], [10, 2], [10, 0], [6, 2]],
];
const result = solve(rootHand, rootTable, oppTable, false, null, false, 5000, 150, 1);
console.log(`Ran ${result.dets} determinizations in ${result.elapsed.toFixed(1)}s`);
const RSTR = { 11: 'J', 12: 'Q', 13: 'K', 14: 'A' };
const SSTR = 'shdc';
function cardStr(c) { return `${RSTR[c[0]] || c[0]}${SSTR[c[1]]}`; }
for (const r of result.ranked.slice(0, 6)) {
  const desc = r.action[0] === 'burn' ? `BURN ${cardStr(r.action[1])}` : `PLAY ${cardStr(r.action[1])} -> col ${r.action[2] + 1}`;
  console.log(`  ${desc.padEnd(28)} winrate~${r.winRate.toFixed(3)} (n=${r.visits})`);
}
