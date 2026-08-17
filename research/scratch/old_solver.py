"""
OLD (pre-optimization) engine, reconstructed to serve as the baseline
'old robot' for a before/after simulation. Same rules and same MCTS/PIMC
algorithm as solver.py, but WITHOUT this session's two improvements:
  1. deep-copies the whole board on every tree node instead of sharing
     unchanged structure (list-of-lists State + state.clone())
  2. Counter-based hand_rank() used for the opponent-weak-column signal
     instead of a fast category-only function, and recomputed once per
     (card, slot) pair instead of once per slot
  3. random expansion order instead of heuristic-biased expansion order
This is the version your friend was effectively playing with.
"""
import random, math, time, collections
from dataclasses import dataclass

RANKS = list(range(2, 15))
SUITS = range(4)

def make_deck():
    return [(r, s) for r in RANKS for s in SUITS]

def hand_rank(cards):
    ranks = sorted([c[0] for c in cards], reverse=True)
    suits = [c[1] for c in cards]
    n = len(cards)
    rank_counts = collections.Counter(ranks)
    counts = sorted(rank_counts.items(), key=lambda x: (-x[1], -x[0]))
    is_flush = n == 5 and len(set(suits)) == 1
    uniq = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = None
    if n == 5 and len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            is_straight, straight_high = True, uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            is_straight, straight_high = True, 5
    if n < 5:
        cat = 0
        if counts[0][1] == 4: cat = 7
        elif counts[0][1] == 3: cat = 3
        elif counts[0][1] == 2 and len(counts) > 1 and counts[1][1] == 2: cat = 2
        elif counts[0][1] == 2: cat = 1
        return (cat, tuple(r for r, c in counts) + tuple(ranks))
    if is_straight and is_flush: return (8, (straight_high,))
    if counts[0][1] == 4:
        kicker = max(r for r in ranks if r != counts[0][0])
        return (7, (counts[0][0], kicker))
    if counts[0][1] == 3 and counts[1][1] == 2:
        return (6, (counts[0][0], counts[1][0]))
    if is_flush: return (5, tuple(ranks))
    if is_straight: return (4, (straight_high,))
    if counts[0][1] == 3:
        kickers = sorted([r for r in ranks if r != counts[0][0]], reverse=True)
        return (3, (counts[0][0],) + tuple(kickers))
    if counts[0][1] == 2 and counts[1][1] == 2:
        pair_ranks = sorted([counts[0][0], counts[1][0]], reverse=True)
        kicker = max(r for r in ranks if r not in pair_ranks)
        return (2, tuple(pair_ranks) + (kicker,))
    if counts[0][1] == 2:
        kickers = sorted([r for r in ranks if r != counts[0][0]], reverse=True)
        return (1, (counts[0][0],) + tuple(kickers))
    return (0, tuple(ranks))

def partial_strength(cards):
    return hand_rank(cards)[0] if cards else -1   # OLD: full hand_rank every call

def fit_score(card, slot_cards, rank_w=12, suit_w=1, straight_w=0.5, high_w=0.05):
    r, s = card
    if len(slot_cards) >= 5: return -999
    ranks_in = [c[0] for c in slot_cards]
    suits_in = [c[1] for c in slot_cards]
    rc = collections.Counter(ranks_in); sc = collections.Counter(suits_in)   # OLD: Counter
    score = rc.get(r, 0) * rank_w + sc.get(s, 0) * suit_w
    if slot_cards:
        mind = min(abs(r - x) for x in ranks_in)
        if mind <= 4: score += max(0, 5 - mind) * straight_w
    score += r * high_w
    return score

def heuristic_action(hand, own_table, opp_table, burned):
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    if plays_made < 4 and empties:
        c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])
    best = {}
    for c in hand:
        scored = []
        for i in open_slots:
            base = fit_score(c, own_table[i])
            weak_bonus = -partial_strength(opp_table[i]) * 3   # OLD: recomputed per (card, slot)
            scored.append((base + weak_bonus, i))
        scored.sort(reverse=True)
        best[c] = scored[0]
    best_card = max(hand, key=lambda c: best[c][0]); val, slot = best[best_card]
    worst_card = min(hand, key=lambda c: best[c][0]); wval, _ = best[worst_card]
    if not burned and wval < 1.5 and val < 1.5:
        return ('burn', worst_card)
    return ('play', best_card, slot)

@dataclass
class State:
    hands: list
    tables: list
    burned: list
    deck: list
    to_move: int
    done: bool = False

    def clone(self):   # OLD: deep-copies everything every step
        return State(
            hands=[list(self.hands[0]), list(self.hands[1])],
            tables=[[list(c) for c in self.tables[0]], [list(c) for c in self.tables[1]]],
            burned=list(self.burned),
            deck=list(self.deck),
            to_move=self.to_move,
            done=self.done,
        )

def legal_actions(state):
    p = state.to_move
    hand = state.hands[p]
    open_slots = [i for i in range(4) if len(state.tables[p][i]) < 5]
    actions = []
    for c in hand:
        for s in open_slots:
            actions.append(('play', c, s))
    if not state.burned[p]:
        for c in hand:
            actions.append(('burn', c))
    return actions

def step(state, action):
    s = state.clone()
    p = s.to_move
    if action[0] == 'burn':
        s.hands[p].remove(action[1])
        s.burned[p] = True
    else:
        _, c, slot = action
        s.hands[p].remove(c)
        s.tables[p][slot].append(c)
    q = 1 - p
    if s.deck:
        s.hands[q].append(s.deck.pop())
        s.to_move = q
        s.done = False
    else:
        s.done = True
    return s

def is_terminal(state):
    return state.done

def evaluate_terminal(state, root_player):
    wins = [0, 0]
    for i in range(4):
        ra, rb = hand_rank(state.tables[0][i]), hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1
    ra, rb = hand_rank(state.hands[0]), hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1
    elif rb > ra: wins[1] += 1
    if wins[0] >= 3: result = 1
    elif wins[1] >= 3: result = -1
    else: result = 0
    return result if root_player == 0 else -result

def rollout(state):
    s = state
    while not is_terminal(s):
        p = s.to_move
        a = heuristic_action(s.hands[p], s.tables[p], s.tables[1 - p], s.burned[p])
        s = step(s, a)
    return s

class Node:
    __slots__ = ('state', 'parent', 'action', 'children', 'untried', 'visits', 'value', 'player')
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.children = []
        self.untried = legal_actions(state) if not is_terminal(state) else []
        random.shuffle(self.untried)   # OLD: random expansion order, no heuristic bias
        self.visits = 0
        self.value = 0.0
        self.player = state.to_move

def uct_select(node, root_player, c=1.4):
    best, best_score = None, -1e18
    for ch in node.children:
        if ch.visits == 0:
            return ch
        q = ch.value / ch.visits
        q = q if node.player == root_player else -q
        score = q + c * math.sqrt(math.log(node.visits) / ch.visits)
        if score > best_score:
            best_score, best = score, ch
    return best

def mcts_search(root_state, root_player, iterations):
    root = Node(root_state)
    for _ in range(iterations):
        node = root
        while not node.untried and node.children and not is_terminal(node.state):
            node = uct_select(node, root_player)
        if node.untried and not is_terminal(node.state):
            a = node.untried.pop()
            child = Node(step(node.state, a), parent=node, action=a)
            node.children.append(child)
            node = child
        terminal_state = node.state if is_terminal(node.state) else rollout(node.state)
        result = evaluate_terminal(terminal_state, root_player)
        n = node
        while n is not None:
            n.visits += 1
            n.value += result
            n = n.parent
    return {ch.action: (ch.visits, ch.value) for ch in root.children}

def determinize(root_hand, root_table, opp_table, root_burned, root_burn_card, opp_burned, rng):
    assert len(root_hand) == 6
    full_deck = set(make_deck())
    known = set(root_hand)
    for col in root_table: known.update(col)
    for col in opp_table: known.update(col)
    if root_burned and root_burn_card is not None:
        known.add(root_burn_card)
    unseen = list(full_deck - known)
    rng.shuffle(unseen)
    idx = 0
    opp_hand = unseen[idx:idx + 5]; idx += 5
    if opp_burned:
        idx += 1
    remaining_deck = unseen[idx:]
    return State(
        hands=[list(root_hand), opp_hand],
        tables=[[list(c) for c in root_table], [list(c) for c in opp_table]],
        burned=[root_burned, opp_burned],
        deck=remaining_deck,
        to_move=0,
        done=False,
    )

def solve(root_hand, root_table, opp_table, root_burned, root_burn_card, opp_burned,
          time_budget=8.0, iters_per_determinization=150, seed=None, verbose=False):
    rng = random.Random(seed)
    action_stats = collections.defaultdict(lambda: [0, 0.0])
    start = time.time()
    dets = 0
    while time.time() - start < time_budget:
        det_state = determinize(root_hand, root_table, opp_table,
                                 root_burned, root_burn_card, opp_burned, rng)
        stats = mcts_search(det_state, root_player=0, iterations=iters_per_determinization)
        for a, (v, val) in stats.items():
            action_stats[a][0] += v
            action_stats[a][1] += val
        dets += 1
    ranked = []
    for a, (v, val) in action_stats.items():
        win_rate = (val / v + 1) / 2 if v > 0 else 0.5
        ranked.append((a, win_rate, v))
    ranked.sort(key=lambda x: x[1], reverse=True)
    elapsed = time.time() - start
    return ranked, dets, elapsed

def card_str(c):
    r, s = c
    rstr = {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}.get(r, str(r))
    return f"{rstr}{'shdc'[s]}"

def format_action(a):
    if a[0] == 'burn':
        return f"BURN {card_str(a[1])}"
    return f"PLAY {card_str(a[1])} -> column {a[2] + 1}"
