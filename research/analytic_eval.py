"""
Analytic (hypergeometric) leaf evaluator -- replaces the rollout-to-terminal
step in MCTS with a closed-form estimate of position value.

CORE IDEA
---------
For a partial column with `c` cards already sharing a dominant rank R, and
`remaining_slots` still open, the question "how many more R's will I get"
is exactly the classic hypergeometric setup: draw N cards without
replacement from a population of size M containing K successes (K = copies
of R still unseen), where N is how many more cards THIS player will
personally draw before the game ends (= their remaining turns).

Within one MCTS determinization, the "population" is the specific
remaining shuffled deck for that determinization (deck_cards[deck_pos:]).
Since that order is itself an arbitrary random guess, treating a player's
future N draws as a uniformly random N-card subset of it (rather than the
exact alternating positions) is not an extra approximation on top of an
already-random guess -- it's the same distribution.

This intentionally ignores flush/straight potential (already shown to be a
minor, usually-negative contributor relative to rank-stacking) and treats
"higher final count of the dominant rank" as a monotonic proxy for column
strength (ignores kicker/two-pair/full-house nuance) in exchange for being
O(1) instead of O(~40 simulated turns) per evaluation.
"""

import math, collections
from solver import hand_rank


# ----------------------------------------------------------------------
# Hypergeometric primitives
# ----------------------------------------------------------------------
def hypergeom_pmf(K, M, N, k):
    """P(exactly k successes) drawing N from population M with K successes,
    without replacement. Standard formula: C(K,k)*C(M-K,N-k) / C(M,N)."""
    if M <= 0 or N <= 0:
        return 1.0 if k == 0 else 0.0
    if k < 0 or k > K or k > N or (N - k) > (M - K):
        return 0.0
    return (math.comb(K, k) * math.comb(M - K, N - k)) / math.comb(M, N)


def hypergeom_dist(K, M, N):
    """Full PMF as a dict {k: probability} for k=0..min(K,N)."""
    lo = max(0, N - (M - K))
    hi = min(K, N)
    return {k: hypergeom_pmf(K, M, N, k) for k in range(lo, hi + 1)}


# ----------------------------------------------------------------------
# Per-column final-count distribution
# ----------------------------------------------------------------------
def column_count_distribution(column_cards, hand_cards, remaining_slots, pool_rank_counts, pool_size, own_remaining_draws):
    """
    Returns (dist, dominant_rank) where dist is {final_count: probability}
    for how this column is likely to resolve.

    - column_cards: cards already played into this column
    - hand_cards: cards currently in the player's hand (not yet played) --
      counted as "free" additions if they match, since they're already in
      hand and don't need to be drawn
    - remaining_slots: 5 - len(column_cards)
    - pool_rank_counts: {rank: count} of the SHARED remaining unseen deck
      for this determinization
    - pool_size: total cards left in that pool
    - own_remaining_draws: how many more cards this player will personally
      draw before the game ends (their remaining turns)
    """
    if remaining_slots == 0:
        counts = collections.Counter(r for r, s in column_cards)
        dom_rank, dom_count = (counts.most_common(1)[0] if counts else (None, 0))
        return {dom_count: 1.0}, dom_rank

    col_counts = collections.Counter(r for r, s in column_cards)
    if col_counts:
        dom_rank, cur_count = col_counts.most_common(1)[0]
    else:
        hand_counts = collections.Counter(r for r, s in hand_cards)
        dom_rank = hand_counts.most_common(1)[0][0] if hand_counts else None
        cur_count = 0

    if dom_rank is None:
        return {0: 1.0}, None

    hand_matching = sum(1 for r, s in hand_cards if r == dom_rank)
    free_adds = min(remaining_slots, hand_matching)
    slots_needing_draws = remaining_slots - free_adds

    K = pool_rank_counts.get(dom_rank, 0)
    M = pool_size
    N = own_remaining_draws

    draw_dist = hypergeom_dist(K, M, N)

    final_dist = collections.defaultdict(float)
    for k, p in draw_dist.items():
        placed = min(k, slots_needing_draws)
        final_count = min(cur_count + free_adds + placed, 4)
        final_dist[final_count] += p
    total = sum(final_dist.values())
    if total > 0:
        final_dist = {k: v / total for k, v in final_dist.items()}
    return dict(final_dist), dom_rank


def column_win_prob(my_dist, opp_dist):
    """P(my final count > opp final count) + 0.5 * P(tie)."""
    p_win = 0.0
    p_tie = 0.0
    for mc, mp in my_dist.items():
        for oc, op in opp_dist.items():
            if mc > oc: p_win += mp * op
            elif mc == oc: p_tie += mp * op
    return p_win + 0.5 * p_tie


# ----------------------------------------------------------------------
# Full position evaluator
# ----------------------------------------------------------------------
def evaluate_position_analytic(state, root_player):
    """Returns a value in [-1, 1] estimating root_player's expected outcome,
    WITHOUT simulating any further turns -- replaces rollout()+evaluate_terminal()."""
    opp = 1 - root_player
    pool = state.deck_cards[state.deck_pos:]
    pool_rank_counts = collections.Counter(r for r, s in pool)
    pool_size = len(pool)

    def remaining_turns(p):
        played = sum(len(c) for c in state.tables[p])
        burned = 1 if state.burned[p] else 0
        return max(0, 21 - played - burned)

    root_draws = remaining_turns(root_player)
    opp_draws = remaining_turns(opp)

    per_subhand_win_prob = []
    for i in range(4):
        root_col = state.tables[root_player][i]
        opp_col = state.tables[opp][i]
        if len(root_col) == 5 and len(opp_col) == 5:
            ra, rb = hand_rank(root_col), hand_rank(opp_col)
            p = 1.0 if ra > rb else (0.0 if rb > ra else 0.5)
        else:
            root_dist, _ = column_count_distribution(
                root_col, state.hands[root_player], 5 - len(root_col),
                pool_rank_counts, pool_size, root_draws)
            opp_dist, _ = column_count_distribution(
                opp_col, state.hands[opp], 5 - len(opp_col),
                pool_rank_counts, pool_size, opp_draws)
            p = column_win_prob(root_dist, opp_dist)
        per_subhand_win_prob.append(p)

    # Hidden hand: composition churns over the rest of the game (cards
    # enter via draws, leave via being played elsewhere), so it doesn't fit
    # the "column fills monotonically" model. Use the CURRENT hand's
    # category as a static proxy -- a simplification, flagged for future
    # refinement.
    ra, rb = hand_rank(state.hands[root_player]), hand_rank(state.hands[opp])
    p5 = 1.0 if ra > rb else (0.0 if rb > ra else 0.5)
    per_subhand_win_prob.append(p5)

    # P(root wins >= 3 of 5), treating the 5 sub-hands as independent
    # Bernoulli trials with DIFFERENT probabilities (Poisson binomial) --
    # exact via brute-force enumeration of all 32 combinations.
    p_majority = 0.0
    for mask in range(32):
        prob = 1.0
        wins = 0
        for i in range(5):
            if mask & (1 << i):
                prob *= per_subhand_win_prob[i]
                wins += 1
            else:
                prob *= (1 - per_subhand_win_prob[i])
        if wins >= 3:
            p_majority += prob

    return 2 * p_majority - 1


# ----------------------------------------------------------------------
# MCTS variant using the analytic evaluator instead of rollout-to-terminal
# ----------------------------------------------------------------------
from solver import is_terminal, step, Node, uct_select, evaluate_terminal

def mcts_search_analytic(root_state, root_player, iterations):
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
        if is_terminal(node.state):
            result = evaluate_terminal(node.state, root_player)
        else:
            result = evaluate_position_analytic(node.state, root_player)
        n = node
        while n is not None:
            n.visits += 1
            n.value += result
            n = n.parent
    return {ch.action: (ch.visits, ch.value) for ch in root.children}
