// ---- core game logic (will be embedded in the HTML artifact) ----
function handRank(cards) {
  const ranks = cards.map(c => c.r).sort((a,b)=>b-a);
  const suits = cards.map(c => c.s);
  const n = cards.length;
  const rankCounts = {};
  for (const r of ranks) rankCounts[r] = (rankCounts[r]||0)+1;
  const counts = Object.entries(rankCounts).map(([r,c])=>[+r,c])
    .sort((a,b)=> b[1]-a[1] || b[0]-a[0]);
  const isFlush = n===5 && new Set(suits).size===1;
  const uniq = [...new Set(ranks)].sort((a,b)=>b-a);
  let isStraight=false, straightHigh=null;
  if (n===5 && uniq.length===5) {
    if (uniq[0]-uniq[4]===4) { isStraight=true; straightHigh=uniq[0]; }
    else if (uniq.join(',')==='14,5,4,3,2') { isStraight=true; straightHigh=5; }
  }
  if (n<5) {
    let cat=0;
    if (counts[0][1]===4) cat=7;
    else if (counts[0][1]===3) cat=3;
    else if (counts[0][1]===2 && counts.length>1 && counts[1][1]===2) cat=2;
    else if (counts[0][1]===2) cat=1;
    return [cat, counts.map(c=>c[0]).concat(ranks)];
  }
  if (isStraight && isFlush) return [8, [straightHigh]];
  if (counts[0][1]===4) {
    const kicker = Math.max(...ranks.filter(r=>r!==counts[0][0]));
    return [7, [counts[0][0], kicker]];
  }
  if (counts[0][1]===3 && counts[1][1]===2) return [6, [counts[0][0], counts[1][0]]];
  if (isFlush) return [5, ranks];
  if (isStraight) return [4, [straightHigh]];
  if (counts[0][1]===3) {
    const kickers = ranks.filter(r=>r!==counts[0][0]).sort((a,b)=>b-a);
    return [3, [counts[0][0], ...kickers]];
  }
  if (counts[0][1]===2 && counts[1][1]===2) {
    const pairRanks = [counts[0][0], counts[1][0]].sort((a,b)=>b-a);
    const kicker = Math.max(...ranks.filter(r=>!pairRanks.includes(r)));
    return [2, [...pairRanks, kicker]];
  }
  if (counts[0][1]===2) {
    const kickers = ranks.filter(r=>r!==counts[0][0]).sort((a,b)=>b-a);
    return [1, [counts[0][0], ...kickers]];
  }
  return [0, ranks];
}
function cmpRank(a,b){
  const [ca,ta]=a, [cb,tb]=b;
  if (ca!==cb) return ca-cb;
  const len=Math.max(ta.length,tb.length);
  for (let i=0;i<len;i++){
    const x=ta[i]??-1, y=tb[i]??-1;
    if (x!==y) return x-y;
  }
  return 0;
}

// sanity tests
const pair = [{r:10,s:0},{r:10,s:1},{r:3,s:2},{r:7,s:3},{r:9,s:0}];
const twopair = [{r:10,s:0},{r:10,s:1},{r:3,s:2},{r:3,s:3},{r:9,s:0}];
const trips = [{r:10,s:0},{r:10,s:1},{r:10,s:2},{r:3,s:3},{r:9,s:0}];
const straight = [{r:5,s:0},{r:6,s:1},{r:7,s:2},{r:8,s:3},{r:9,s:0}];
const flush = [{r:2,s:0},{r:5,s:0},{r:9,s:0},{r:11,s:0},{r:13,s:0}];
const fullhouse = [{r:10,s:0},{r:10,s:1},{r:10,s:2},{r:3,s:3},{r:3,s:0}];
const quads = [{r:10,s:0},{r:10,s:1},{r:10,s:2},{r:10,s:3},{r:3,s:0}];
const sf = [{r:5,s:0},{r:6,s:0},{r:7,s:0},{r:8,s:0},{r:9,s:0}];
const high = [{r:2,s:0},{r:5,s:1},{r:9,s:2},{r:11,s:3},{r:13,s:0}];
const hands = {pair,twopair,trips,straight,flush,fullhouse,quads,sf,high};
for (const [name,h] of Object.entries(hands)) console.log(name, JSON.stringify(handRank(h)));

// ordering check
const order = ['high','pair','twopair','trips','straight','flush','fullhouse','quads','sf'];
for (let i=0;i<order.length-1;i++){
  const a = handRank(hands[order[i]]), b = handRank(hands[order[i+1]]);
  console.log(order[i], '<', order[i+1], '?', cmpRank(a,b) < 0);
}

// ---- rest of engine ----
function makeDeck(){
  const d=[];
  for (let r=2;r<=14;r++) for (let s=0;s<4;s++) d.push({r,s});
  return d;
}
function partialStrength(cards){ return cards.length? handRank(cards)[0] : -1; }
function fitScore(card, slotCards, rankW=12, suitW=1, straightW=0.5, highW=0.05){
  if (slotCards.length>=5) return -999;
  const ranksIn = slotCards.map(c=>c.r), suitsIn = slotCards.map(c=>c.s);
  const rc={}, sc={};
  for (const r of ranksIn) rc[r]=(rc[r]||0)+1;
  for (const s of suitsIn) sc[s]=(sc[s]||0)+1;
  let score = (rc[card.r]||0)*rankW + (sc[card.s]||0)*suitW;
  if (slotCards.length){
    const mind = Math.min(...ranksIn.map(x=>Math.abs(card.r-x)));
    if (mind<=4) score += Math.max(0,5-mind)*straightW;
  }
  score += card.r*highW;
  return score;
}
function heuristicAction(hand, ownTable, oppTable, burned){
  const openSlots=[0,1,2,3].filter(i=>ownTable[i].length<5);
  if (!openSlots.length) return {type:'burn', card:hand[0]};
  const playsMade = ownTable.reduce((a,s)=>a+s.length,0);
  const empties = [0,1,2,3].filter(i=>ownTable[i].length===0);
  if (playsMade<4 && empties.length){
    const c = hand.reduce((m,c)=> c.r<m.r?c:m);
    return {type:'play', card:c, slot:empties[0]};
  }
  const best={};
  for (const c of hand){
    let scored = openSlots.map(i=>{
      const base = fitScore(c, ownTable[i]);
      const weakBonus = -partialStrength(oppTable[i])*3;
      return [base+weakBonus, i];
    });
    scored.sort((a,b)=>b[0]-a[0]);
    best[cardKey(c)] = scored[0];
  }
  let bestCard = hand[0], bestVal=-Infinity;
  for (const c of hand){ const [v]=best[cardKey(c)]; if (v>bestVal){bestVal=v;bestCard=c;} }
  let worstCard = hand[0], worstVal=Infinity;
  for (const c of hand){ const [v]=best[cardKey(c)]; if (v<worstVal){worstVal=v;worstCard=c;} }
  const [val,slot] = best[cardKey(bestCard)];
  const [wval] = best[cardKey(worstCard)];
  if (!burned && wval<1.5 && val<1.5) return {type:'burn', card:worstCard};
  return {type:'play', card:bestCard, slot};
}
function cardKey(c){ return c.r+'-'+c.s; }

function cloneState(s){
  return {
    hands:[s.hands[0].map(c=>({...c})), s.hands[1].map(c=>({...c}))],
    tables:[s.tables[0].map(col=>col.map(c=>({...c}))), s.tables[1].map(col=>col.map(c=>({...c})))],
    burned:[...s.burned],
    deck: s.deck.map(c=>({...c})),
    toMove: s.toMove,
  };
}
function legalActions(state){
  const p = state.toMove;
  const hand = state.hands[p];
  const openSlots = [0,1,2,3].filter(i=>state.tables[p][i].length<5);
  const actions=[];
  for (const c of hand) for (const s of openSlots) actions.push({type:'play', card:c, slot:s});
  if (!state.burned[p]) for (const c of hand) actions.push({type:'burn', card:c});
  return actions;
}
function actionKey(a){ return a.type==='burn' ? `burn:${cardKey(a.card)}` : `play:${cardKey(a.card)}:${a.slot}`; }
function removeCard(arr, c){
  const idx = arr.findIndex(x=>x.r===c.r && x.s===c.s);
  arr.splice(idx,1);
}
function step(state, action){
  const s = cloneState(state);
  const p = s.toMove;
  if (action.type==='burn'){
    removeCard(s.hands[p], action.card);
    s.burned[p]=true;
  } else {
    removeCard(s.hands[p], action.card);
    s.tables[p][action.slot].push(action.card);
  }
  if (s.deck.length) s.hands[p].push(s.deck.pop());
  s.toMove = 1-p;
  return s;
}
function isTerminal(state){ return state.deck.length===0; }
function evaluateTerminal(state, rootPlayer){
  let wins=[0,0];
  for (let i=0;i<4;i++){
    const ra=handRank(state.tables[0][i]), rb=handRank(state.tables[1][i]);
    const c = cmpRank(ra,rb);
    if (c>0) wins[0]++; else if (c<0) wins[1]++;
  }
  const ra=handRank(state.hands[0]), rb=handRank(state.hands[1]);
  const c = cmpRank(ra,rb);
  if (c>0) wins[0]++; else if (c<0) wins[1]++;
  let result = wins[0]>=3 ? 1 : (wins[1]>=3 ? -1 : 0);
  return rootPlayer===0 ? result : -result;
}
function rollout(state){
  let s = state;
  while (!isTerminal(s)){
    const p = s.toMove;
    const a = heuristicAction(s.hands[p], s.tables[p], s.tables[1-p], s.burned[p]);
    s = step(s, a);
  }
  return s;
}

function shuffle(arr, rng){
  for (let i=arr.length-1;i>0;i--){
    const j = Math.floor(rng()*(i+1));
    [arr[i],arr[j]]=[arr[j],arr[i]];
  }
  return arr;
}
function makeRng(seed){
  let x = seed || 123456789;
  return function(){
    x ^= x<<13; x^=x>>>17; x^=x<<5; x|=0;
    return ((x>>>0) / 4294967296);
  };
}

function determinize(rootHand, rootTable, oppTable, rootBurned, rootBurnCard, oppBurned, rng){
  const full = makeDeck();
  const knownKeys = new Set();
  for (const c of rootHand) knownKeys.add(cardKey(c));
  for (const col of rootTable) for (const c of col) knownKeys.add(cardKey(c));
  for (const col of oppTable) for (const c of col) knownKeys.add(cardKey(c));
  if (rootBurned && rootBurnCard) knownKeys.add(cardKey(rootBurnCard));
  let unseen = full.filter(c=>!knownKeys.has(cardKey(c)));
  shuffle(unseen, rng);
  let idx=0;
  const oppHand = unseen.slice(idx, idx+5); idx+=5;
  if (oppBurned) idx+=1;
  const deck = unseen.slice(idx);
  return {
    hands: [rootHand.map(c=>({...c})), oppHand],
    tables: [rootTable.map(col=>col.map(c=>({...c}))), oppTable.map(col=>col.map(c=>({...c})))],
    burned: [rootBurned, oppBurned],
    deck,
    toMove: 0,
  };
}

function newNode(state, parent, action){
  return {
    state, parent, action,
    children: [],
    untried: isTerminal(state) ? [] : legalActions(state),
    visits:0, value:0,
    player: state.toMove,
  };
}
function uctSelect(node, rootPlayer, c=1.4){
  let best=null, bestScore=-Infinity;
  for (const ch of node.children){
    if (ch.visits===0) return ch;
    let q = ch.value/ch.visits;
    q = (node.player===rootPlayer) ? q : -q;
    const score = q + c*Math.sqrt(Math.log(node.visits)/ch.visits);
    if (score>bestScore){ bestScore=score; best=ch; }
  }
  return best;
}
function mctsSearch(rootState, rootPlayer, iterations, rng){
  const root = newNode(rootState, null, null);
  shuffle(root.untried, rng);
  for (let it=0; it<iterations; it++){
    let node = root;
    while (node.untried.length===0 && node.children.length>0 && !isTerminal(node.state)){
      node = uctSelect(node, rootPlayer);
    }
    if (node.untried.length>0 && !isTerminal(node.state)){
      const a = node.untried.pop();
      const child = newNode(step(node.state, a), node, a);
      shuffle(child.untried, rng);
      node.children.push(child);
      node = child;
    }
    const terminalState = isTerminal(node.state) ? node.state : rollout(node.state);
    const result = evaluateTerminal(terminalState, rootPlayer);
    let n = node;
    while (n){ n.visits++; n.value += result; n = n.parent; }
  }
  const stats = new Map();
  for (const ch of root.children) stats.set(actionKey(ch.action), [ch.visits, ch.value, ch.action]);
  return stats;
}

async function solveBoard(rootHand, rootTable, oppTable, rootBurned, rootBurnCard, oppBurned,
                           timeBudgetMs, itersPerDet, seed, onProgress){
  const rng = makeRng(seed || Date.now());
  const actionStats = new Map();
  const start = Date.now();
  let dets=0;
  while (Date.now()-start < timeBudgetMs){
    const det = determinize(rootHand, rootTable, oppTable, rootBurned, rootBurnCard, oppBurned, rng);
    const stats = mctsSearch(det, 0, itersPerDet, rng);
    for (const [key,[v,val,action]] of stats){
      if (!actionStats.has(key)) actionStats.set(key, [0,0,action]);
      const e = actionStats.get(key);
      e[0]+=v; e[1]+=val;
    }
    dets++;
    if (onProgress) onProgress(dets, Date.now()-start);
  }
  const ranked = [...actionStats.entries()].map(([key,[v,val,action]])=>{
    const winRate = v>0 ? (val/v+1)/2 : 0.5;
    return {action, winRate, visits:v};
  });
  ranked.sort((a,b)=>b.winRate-a.winRate);
  return {ranked, dets, elapsed: Date.now()-start};
}

// ---- quick end-to-end test ----
(async () => {
  const rootHand  = [{r:7,s:0},{r:11,s:0},{r:10,s:3},{r:9,s:0},{r:5,s:0}];
  const rootTable = [
    [{r:2,s:3},{r:13,s:3},{r:14,s:3},{r:14,s:0},{r:12,s:3}],
    [{r:4,s:1}],
    [{r:5,s:1},{r:8,s:1},{r:8,s:2},{r:5,s:3},{r:12,s:1}],
    [{r:3,s:1}],
  ];
  const oppTable  = [
    [{r:3,s:0}],
    [{r:3,s:2},{r:3,s:3},{r:13,s:2},{r:12,s:2}],
    [{r:2,s:2},{r:2,s:1}],
    [{r:7,s:3},{r:8,s:3},{r:10,s:2},{r:10,s:0},{r:6,s:2}],
  ];
  const res = await solveBoard(rootHand, rootTable, oppTable, false, null, false, 3000, 100, 1);
  console.log(`\ndets=${res.dets} elapsed=${res.elapsed}ms`);
  for (const {action, winRate, visits} of res.ranked.slice(0,6)){
    console.log(actionKey(action), winRate.toFixed(3), visits);
  }
})();
