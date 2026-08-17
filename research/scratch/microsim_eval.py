"""
Micro-simulation leaf evaluator (v2) -- fixes the biggest suspected flaw in
the v1 analytic evaluator: treating the 4 columns + hidden hand as
independent, when they actually compete for the same pool of future draws.

CORE IDEA
---------
Instead of computing a closed-form probability per column in isolation
(v1), simulate a plausible ALLOCATION in one shot: sample this player's
future draws from the unseen pool, combine with their current hand, and
greedily assign the whole pool across their real columns using the same
fit-score logic the actual heuristic policy uses -- so a card can only go
to ONE column, exactly like the real game, and columns genuinely compete
for good cards instead of each being scored as if it had exclusive access
to the future.

This is still far cheaper than a full rollout: no turn alternation, no
simulating the opponent's actual move-by-move decisions, no burn-timing
logic beyond a simple worst-card rule -- just "given the cards I'll ever
see, how do they best sort into my real columns," computed directly.
"""

import random, collections
from solver import hand_rank, fit_score, is_terminal, step, Node, uct_select, evaluate_terminal


def greedy_allocate(current_hand, current_table, future_draws, burned):
    """Greedily assign current_hand + future_draws across the open table
    slots (using fit_score, same logic the real heuristic policy uses),
    then burn the single worst leftover card if burn hasn't been used yet.
    Returns (final_table, final_hand).

    Single-pass O(pool * 4): process cards in an order that puts likely
    synergy cards first (grouped by rank, largest groups first, so pairs/
    trips/quads land together), and for EACH card just pick its best
    CURRENTLY open column once -- no repeated full rescans of the whole
    remaining pool at every step, which is what made the first version an
    order of magnitude slower than the rollout it was meant to replace."""
    pool = list(current_hand) + list(future_draws)
    table = [list(col) for col in current_table]
    remaining_slots = [5 - len(c) for c in table]
    total_needed = sum(remaining_slots)

    # Order: biggest same-rank clusters first (so a pair/trip/quad's cards
    # get placed consecutively into the same column while it's still open),
    # then everything else by rank (mild high-card preference, matches
    # fit_score's own tie-break).
    rank_counts = collections.Counter(r for r, s in pool)
    order = sorted(range(len(pool)), key=lambda i: (-rank_counts[pool[i][0]], -pool[i][0]))

    empty_cols = set(ci for ci in range(4) if len(table[ci]) == 0 and remaining_slots[ci] > 0)
    placed = 0
    placed_idx = []
    for idx in order:
        if placed >= total_needed:
            break
        card = pool[idx]
        # Prefer a column that's still completely untouched (validated
        # opening principle) UNLESS an already-started column offers a
        # clearly better fit (a real synergy match beats blind spreading).
        best_ci, best_score = None, -1e18
        for ci in range(4):
            if remaining_slots[ci] <= 0:
                continue
            score = fit_score(card, table[ci])
            if ci in empty_cols:
                score += 6  # modest nudge toward untouched columns, not an override
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


def evaluate_position_microsim(state, root_player, n_samples=25, rng=None):
    """Returns a value in [-1, 1]. For each of n_samples: sample both
    players' future draws from the shared unseen pool (disjoint, matching
    determinize()'s own logic), greedily allocate each player's own
    hand+draws across their own real columns, then score the resulting
    complete position exactly (real hand_rank comparisons, not proxies).
    Average the +1/-1/0 results -- same backprop convention as the
    rollout-based evaluator."""
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

    total = 0.0
    for _ in range(n_samples):
        shuffled = pool[:]
        rng.shuffle(shuffled)
        root_future = shuffled[:n_root]
        opp_future = shuffled[n_root:n_root + n_opp]

        root_table, root_hand = greedy_allocate(
            state.hands[root_player], state.tables[root_player], root_future, state.burned[root_player])
        opp_table, opp_hand = greedy_allocate(
            state.hands[opp], state.tables[opp], opp_future, state.burned[opp])

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


# ----------------------------------------------------------------------
# MCTS variant using the micro-simulation evaluator at leaves
# ----------------------------------------------------------------------
def mcts_search_microsim(root_state, root_player, iterations, leaf_samples=25):
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
            result = evaluate_position_microsim(node.state, root_player, n_samples=leaf_samples, rng=rng)
        n = node
        while n is not None:
            n.visits += 1
            n.value += result
            n = n.parent
    return {ch.action: (ch.visits, ch.value) for ch in root.children}
