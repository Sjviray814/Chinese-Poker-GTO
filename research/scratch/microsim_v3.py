"""
Whole-board probabilistic evaluator (v3) -- combines the two validated
pieces from this session instead of re-deriving either from scratch:

1. From microsim_eval.py (v2): sample each player's own future draws from
   the shared unseen pool and greedily allocate the WHOLE board at once
   (all 4 columns + hidden hand together, correctly modeling that a card
   can only go to ONE place, i.e. columns genuinely compete for good
   cards) -- this replaces the expensive turn-by-turn rollout with a
   single-shot allocation, without needing to simulate alternating turns.

2. From prob_fitscore.py (this session's long debugging arc): the actual
   per-placement scoring used during that allocation is the VALIDATED
   heuristic_action_v2 logic -- probability-informed fit_score (real
   hypergeometric completion odds instead of a flat constant, with the
   four bugs found and fixed: no speculative credit for empty columns or
   non-matching cards, no false credit for cards still sitting in hand,
   correct tie-breaking when several ranks are tied) PLUS the
   opponent-aware weak_bonus term that v2 was missing entirely -- which
   is the single most validated lever in this whole project (measured at
   a 64-70% win-rate contributor, way back near the start of this
   session).

The result: allocate a full hypothetical final board for BOTH players in
one shot per sample, using real opponent-aware, probability-aware
decisions throughout, average over K samples, and compare the resulting
complete boards exactly (real hand_rank, not a proxy).
"""

import random, collections
from solver import hand_rank, partial_strength, is_terminal, step, Node, uct_select, evaluate_terminal
from prob_fitscore import probability_informed_fit_score, apparent_pool


def scored_allocate(current_hand, current_table, opp_table, future_draws, burned,
                     pool_rank_counts, pool_size, own_future_draws_remaining):
    """Like microsim_eval.greedy_allocate, but scores each candidate
    placement with the FULL validated heuristic_action_v2 logic (real
    probability + opponent-aware weak_bonus) instead of the flat fit_score
    v2 originally used."""
    pool = list(current_hand) + list(future_draws)
    table = [list(col) for col in current_table]
    remaining_slots = [5 - len(c) for c in table]
    total_needed = sum(remaining_slots)

    rank_counts = collections.Counter(r for r, s in pool)
    order = sorted(range(len(pool)), key=lambda i: (-rank_counts[pool[i][0]], -pool[i][0]))

    empty_cols = set(ci for ci in range(4) if len(table[ci]) == 0 and remaining_slots[ci] > 0)
    placed = 0
    placed_idx = []
    for idx in order:
        if placed >= total_needed:
            break
        card = pool[idx]
        best_ci, best_score = None, -1e18
        for ci in range(4):
            if remaining_slots[ci] <= 0:
                continue
            # own_future_draws_remaining shrinks as the allocation proceeds --
            # each already-placed card represents one turn already spent.
            draws_left = max(0, own_future_draws_remaining - placed)
            score = probability_informed_fit_score(
                card, table[ci], pool, pool_rank_counts, pool_size, draws_left)
            weak_bonus = -partial_strength(opp_table[ci]) * 3   # the critical missing piece from v2
            if ci in empty_cols:
                score += 6
            score += weak_bonus
            if score > best_score:
                best_score, best_ci = score, ci
        if best_ci is None:
            break
        table[best_ci].append(card)
        remaining_slots[best_ci] -= 1
        empty_cols.discard(best_ci)
        placed_idx.append(idx)
        placed += 1

    placed_set = set(placed_idx)
    leftover = [i for i in range(len(pool)) if i not in placed_set]
    if not burned and leftover:
        worst_idx = min(leftover, key=lambda i: pool[i][0])
        leftover.remove(worst_idx)

    final_hand = [pool[i] for i in leftover]
    return table, final_hand


def evaluate_position_v3(state, root_player, n_samples=8, rng=None):
    """Returns a value in [-1, 1]. Same sampling structure as v2's
    evaluate_position_microsim, but allocation now uses the validated,
    opponent-aware, probability-informed scorer instead of flat fit_score."""
    if rng is None:
        rng = random.Random()
    opp = 1 - root_player
    pool = list(state.deck_cards[state.deck_pos:])

    def future_draws_count(p):
        played = sum(len(c) for c in state.tables[p])
        burned = 1 if state.burned[p] else 0
        remaining_turns = max(0, 21 - played - burned)
        already_drawn_this_turn = 1 if len(state.hands[p]) == 6 else 0
        return max(0, remaining_turns - already_drawn_this_turn)

    n_root = future_draws_count(root_player)
    n_opp = future_draws_count(opp)

    # Apparent pool composition, from each player's OWN knowledge -- computed
    # once per evaluation call (doesn't change across the K samples, only
    # WHICH cards land where does).
    root_pool_counts, root_pool_size = apparent_pool(
        state.hands[root_player], state.tables[root_player], state.tables[opp],
        state.burned[root_player], None)
    opp_pool_counts, opp_pool_size = apparent_pool(
        state.hands[opp], state.tables[opp], state.tables[root_player],
        state.burned[opp], None)

    total = 0.0
    for _ in range(n_samples):
        shuffled = pool[:]
        rng.shuffle(shuffled)
        root_future = shuffled[:n_root]
        opp_future = shuffled[n_root:n_root + n_opp]

        root_table, root_hand = scored_allocate(
            state.hands[root_player], state.tables[root_player], state.tables[opp],
            root_future, state.burned[root_player], root_pool_counts, root_pool_size, n_root)
        opp_table, opp_hand = scored_allocate(
            state.hands[opp], state.tables[opp], state.tables[root_player],
            opp_future, state.burned[opp], opp_pool_counts, opp_pool_size, n_opp)

        wins = [0, 0]
        for i in range(4):
            ra, rb = hand_rank(root_table[i]), hand_rank(opp_table[i])
            if ra > rb: wins[0] += 1
            elif rb > ra: wins[1] += 1
        ra, rb = hand_rank(root_hand), hand_rank(opp_hand)
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1

        if wins[0] >= 3: result = 1
        elif wins[1] >= 3: result = -1
        else: result = 0
        total += result

    return total / n_samples


def mcts_search_v3(root_state, root_player, iterations, leaf_samples=8):
    root = Node(root_state)
    rng = random.Random()
    for _ in range(iterations):
        node = root
        while not node.untried and node.children and not is_terminal(node.state):
            node = uct_select(node, root_player)
        if node.untried and not is_terminal(node.state):
            a = node.untried.pop()
            child = Node(step(node.state, a), parent=node, action=a)
            node.children.append(child)
            node = child
        if is_terminal(node.state):
            result = evaluate_terminal(node.state, root_player)
        else:
            result = evaluate_position_v3(node.state, root_player, n_samples=leaf_samples, rng=rng)
        n = node
        while n is not None:
            n.visits += 1
            n.value += result
            n = n.parent
    return {ch.action: (ch.visits, ch.value) for ch in root.children}
