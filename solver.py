"""
Move solver for 2-Player Open-Tableau Poker (52-card exhaustion).

WHY THIS APPROACH
------------------
The full game tree is enormous (branching factor ~5-25 per turn, up to ~40
plies remaining) AND the game has hidden information (opponent's hand, both
burn cards, deck order) -- so plain minimax/alpha-beta over the true game is
both computationally infeasible and technically the wrong tool (it assumes
perfect information).

The standard fix, used by strong AI for bridge, skat, and other
hidden-information card games, is:

  1. DETERMINIZATION: randomly deal the cards you can't see (opponent's
     hand, opponent's burn card if used, and the deck order) in a way
     that's consistent with everything you *do* know (which cards have
     already appeared, exact counts remaining, etc). This turns the hidden
     game into an ordinary fully-observed game.

  2. SEARCH: run Monte Carlo Tree Search (UCT) on that fully-observed game
     to find a strong move for THIS determinization.

  3. REPEAT: sample many different determinizations (many different
     "guesses" at the hidden cards) and average the results. This is
     "Perfect Information Monte Carlo" (PIMC) search. Root actions are
     always the same set of moves (they only depend on your own hand,
     which you always know), so results aggregate cleanly across samples.

  4. ANYTIME BUDGET: the whole thing runs in a loop bounded by a wall-clock
     time budget, so it searches "as deep as possible" for however long you
     let it -- more time = more determinizations x more MCTS iterations =
     a better approximation of optimal play, with no hard depth ceiling.

Rollouts beyond the search tree horizon are completed using the
"attack-the-opponent's-weak-column, rank-synergy-first" heuristic policy
developed and validated earlier (it beat plain random play ~94% of the
time, and beat naive hand-hoarding ~99% of the time), which makes the
Monte Carlo estimates far less noisy than random rollouts.

TURN ORDER
----------
Each turn the active player DRAWS FIRST, then decides what to play/burn
from their now-6-card hand, ending the turn back at 5. So at the moment
you're asking "what's my best move," your hand already includes this
turn's draw -- it should have 6 cards, not 5.
"""

import random, math, time, collections, functools
from dataclasses import dataclass, field

# ----------------------------------------------------------------------
# Cards & hand evaluation
# ----------------------------------------------------------------------
RANKS = list(range(2, 15))  # 11=J 12=Q 13=K 14=A
SUITS = range(4)

def make_deck():
    return [(r, s) for r in RANKS for s in SUITS]

_FULL_DECK = tuple(make_deck())  # precomputed once; determinize() reuses this instead of rebuilding it every call

def hand_rank(cards):
    """Standard 5-card poker hand ranking (also degrades gracefully for
    partial <5-card hands, used only for in-progress evaluation)."""
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
    """Fast partial-hand CATEGORY only (0-7) -- used purely as a heuristic
    signal (e.g. 'is this column weak'), not for tie-breaking, so it skips
    straight/flush checks and Counter entirely in favor of a plain dict."""
    if not cards:
        return -1
    counts = {}
    for r, s in cards:
        counts[r] = counts.get(r, 0) + 1
    vals = sorted(counts.values(), reverse=True)
    if vals[0] == 4: return 7
    if vals[0] == 3: return 3
    if vals[0] == 2 and len(vals) > 1 and vals[1] == 2: return 2
    if vals[0] == 2: return 1
    return 0

# ----------------------------------------------------------------------
# Heuristic policy (used for rollouts past the search horizon)
# ----------------------------------------------------------------------
def fit_score(card, slot_cards, rank_w=12, suit_w=1, straight_w=0.0, high_w=0.05, junk_penalty_w=1.5):
    """Used by heuristic_action (the rollout policy). straight_w=0.0 and
    junk_penalty_w are both validated fixes for real, user-reported
    failure modes (confirmed via actual screenshots of live play):

    straight_w defaults to 0.0 (was 0.5) -- the old nonzero value rewarded
    placing rank-ADJACENT (not matching) cards together purely for being
    numerically close, even though this session extensively validated
    that pursuing straights is the single WORST strategy in this game.
    Validated at the MCTS level as a strong win on its own (8-2).

    junk_penalty_w penalizes placing a non-matching card into a column
    that already holds unrelated cards (and has no pair of its own),
    proportional to how many such cards have piled up -- makes an empty
    or less-cluttered column the clear preference over continuing to
    dump unrelated cards together. This needed to be fixed HERE, not just
    in action_priority (which only affects tree exploration order): the
    ACTUAL win-rate estimates that determine the bot's final real move
    come from rollout simulations, i.e. this function. An
    action_priority-only fix left those underlying value estimates
    unchanged -- a junk-tolerant column could still come out looking fine
    to the search once explored, since exploration ORDER alone can't fix
    the VALUE the search assigns to what it finds. Validated at the MCTS
    level as a strong win on its own (8-2). (A THIRD related fix --
    crediting a candidate card for matching another card still in hand,
    not just the board -- was tried here too but found to REGRESS full
    MCTS-level play (33%); it lives only in action_priority's
    fit_score_hand_aware, where it was validated safely instead.)"""
    r, s = card
    n = len(slot_cards)
    if n >= 5: return -999
    rank_matches = sum(1 for rr, ss in slot_cards if rr == r)
    if n == 0:
        return r * high_w
    suit_matches = sum(1 for rr, ss in slot_cards if ss == s)
    mind = min(abs(r - rr) for rr, ss in slot_cards)
    score = rank_matches * rank_w + suit_matches * suit_w
    if mind <= 4: score += (5 - mind) * straight_w
    score += r * high_w
    if rank_matches == 0:
        col_counts = {}
        for rr, ss in slot_cards: col_counts[rr] = col_counts.get(rr, 0) + 1
        col_has_pair = max(col_counts.values()) >= 2 if col_counts else False
        if not col_has_pair:
            score -= n * junk_penalty_w
    return score

# ----------------------------------------------------------------------
# Column win-probability estimator (validated separately this session --
# see column_winprob.py's development history for the full debugging
# arc). Consolidated here, not imported, to keep solver.py self-contained
# and avoid a circular import (column_winprob.py itself imports hand_rank
# from this module).
# ----------------------------------------------------------------------
@functools.lru_cache(maxsize=4096)
def hypergeom_pmf(K, M, N, k):
    """P(exactly k successes) drawing N from population M with K successes,
    without replacement. Standard formula: C(K,k)*C(M-K,N-k) / C(M,N).
    Cached: within one decision, pool_size (M) is constant and
    future_draws (N) only takes 2-3 distinct values, so the same (K,M,N,k)
    combination recurs often across different candidate cards/slots --
    memoizing this pure function avoids redundant math.comb() calls
    without changing any result."""
    if M <= 0 or N <= 0:
        return 1.0 if k == 0 else 0.0
    if k < 0 or k > K or k > N or (N - k) > (M - K):
        return 0.0
    return (math.comb(K, k) * math.comb(M - K, N - k)) / math.comb(M, N)


@functools.lru_cache(maxsize=4096)
def hypergeom_dist(K, M, N):
    """Full PMF as a dict {k: probability} for k=0..min(K,N)."""
    lo = max(0, N - (M - K))
    hi = min(K, N)
    return {k: hypergeom_pmf(K, M, N, k) for k in range(lo, hi + 1)}


@functools.lru_cache(maxsize=4096)
def multivariate_hypergeom_dist(K1, K2, M, N):
    """Joint P(k1 of type1, k2 of type2) drawn among N from a pool of M
    containing K1 type1, K2 type2, rest other. Two ranks developing
    SIMULTANEOUSLY share the same N draws -- modeling them as two
    independent hypergeom_dist calls double-counts the draw budget, which
    specifically inflates the joint "both succeed" outcome, i.e. full
    house. Verified: marginals of this joint distribution match the
    ordinary single-rank hypergeometric exactly, so this is strictly more
    correct, not just different."""
    dist = {}
    for k1 in range(0, min(K1, N) + 1):
        for k2 in range(0, min(K2, N - k1) + 1):
            other_needed = N - k1 - k2
            other_available = M - K1 - K2
            if other_needed < 0 or other_needed > other_available:
                continue
            p = math.comb(K1, k1) * math.comb(K2, k2) * math.comb(other_available, other_needed) / math.comb(M, N)
            dist[(k1, k2)] = p
    return dist


def apparent_pool_with_suits(own_hand, own_table, opp_table_public, own_burned, own_burn_card):
    """Unseen-card composition (rank AND suit counts) from THIS player's
    own knowledge only -- opponent's hand, opponent's burn (if any), and
    the true deck are all equally 'unseen' from here, matching how
    determinize() treats hidden information during search."""
    known = set(own_hand)
    for col in own_table: known.update(col)
    for col in opp_table_public: known.update(col)
    if own_burned and own_burn_card is not None:
        known.add(own_burn_card)
    unseen = [c for c in _FULL_DECK if c not in known]
    rank_counts = collections.Counter(r for r, s in unseen)
    suit_counts = collections.Counter(s for r, s in unseen)
    return rank_counts, suit_counts, len(unseen)


def remaining_turns(own_table, own_burned):
    played = sum(len(c) for c in own_table)
    burned = 1 if own_burned else 0
    return max(0, 21 - played - burned)


def column_count_distribution(column_cards, remaining_slots, pool_rank_counts, pool_size, future_draws):
    """Distribution over {final_count_of_dominant_rank: probability} for
    how this column's dominant rank is likely to resolve.

    Uses `remaining_slots` as the hypergeometric sample size for FLUSH-type
    per-slot capping, but `future_draws` for the underlying draw
    probability -- a player can patiently wait across their ENTIRE
    remaining game for a specific rank and place it whenever it arrives;
    a column can only ever RECEIVE `remaining_slots` more cards, but it
    isn't limited to sampling only its own slot-count's worth of draws.
    Returns (dist, representative_rank, already_categories) -- the last
    flag distinguishes a raw dominant-rank-count distribution (established
    pair branch) from an already-category distribution (no-pair branch,
    which can represent two pair / full house that a single tracked rank
    cannot).
    """
    if remaining_slots == 0:
        counts = collections.Counter(r for r, s in column_cards)
        dom_rank, dom_count = (counts.most_common(1)[0] if counts else (None, 0))
        return {dom_count: 1.0}, dom_rank, False

    col_counts = collections.Counter(r for r, s in column_cards)
    if not col_counts:
        return {0: 1.0}, None, False

    top_count = max(col_counts.values())
    M = pool_size

    if top_count >= 2:
        dom_rank = max(r for r, c in col_counts.items() if c == top_count)
        cur_count = top_count
        K = pool_rank_counts.get(dom_rank, 0)
        draw_dist = hypergeom_dist(K, M, future_draws)
        final_dist = collections.defaultdict(float)
        for k, p in draw_dist.items():
            placed = min(k, remaining_slots)
            final_dist[min(cur_count + placed, 4)] += p
        total = sum(final_dist.values())
        return ({k: v / total for k, v in final_dist.items()} if total > 0 else {cur_count: 1.0}), dom_rank, False

    # No established pair yet -- track the top 2 candidate ranks jointly
    # so two pair / full house emerge naturally from the (count1, count2)
    # combination, rather than being structurally impossible to represent
    # (verified against real simulated play: a plain unpaired 2-card
    # column actually reaches at least a pair 97.5% of the time, with two
    # pair (31%) and full house (10%) alone accounting for 41% of real
    # outcomes -- a single-rank model cannot express this at all).
    distinct_ranks = sorted(col_counts.keys(), key=lambda r: -pool_rank_counts.get(r, 0))[:2]
    if len(distinct_ranks) == 1:
        rank1, rank2 = distinct_ranks[0], None
        K1, K2 = pool_rank_counts.get(rank1, 0), 0
    else:
        rank1, rank2 = distinct_ranks[0], distinct_ranks[1]
        K1, K2 = pool_rank_counts.get(rank1, 0), pool_rank_counts.get(rank2, 0)

    joint_dist = multivariate_hypergeom_dist(K1, K2, M, future_draws)

    cat_dist = collections.defaultdict(float)
    best_rank_by_cat = {}
    for (k1_raw, k2_raw), joint in joint_dist.items():
        k1 = min(k1_raw, remaining_slots)
        k2 = min(k2_raw, remaining_slots - k1) if rank2 is not None else 0
        count1, count2 = 1 + k1, (1 + k2 if rank2 is not None else 0)
        hi, lo = max(count1, count2), min(count1, count2)
        hi_rank = rank1 if count1 >= count2 else rank2
        if hi >= 4: cat = 7
        elif hi == 3 and lo >= 2: cat = 6   # full house
        elif hi == 3: cat = 3
        elif hi == 2 and lo == 2: cat = 2   # two pair
        elif hi == 2: cat = 1
        else: cat = 0
        # Escalating from an already-solid two pair up to full house/quads
        # assumes every matching draw gets greedily committed to THIS
        # column, when a real player is also managing 3 others -- verified
        # this was overestimating full house ~2x (predicted 20.2% vs
        # actual 10.4%) while the TOTAL "both ranks develop" mass was
        # already correct (41.7% vs 41.0%), so only the split needed
        # correcting.
        if cat in (6, 7) and lo >= 2:
            escalate_discount = 0.5
            cat_dist[2] += joint * (1 - escalate_discount)
            best_rank_by_cat.setdefault(2, rank1 if count1 >= 2 else rank2)
            joint = joint * escalate_discount
        cat_dist[cat] += joint
        best_rank_by_cat.setdefault(cat, hi_rank if hi >= 2 else rank1)
    total = sum(cat_dist.values())
    cat_dist = {k: v / total for k, v in cat_dist.items()} if total > 0 else {0: 1.0}
    proxy_rank = best_rank_by_cat.get(max(cat_dist, key=lambda c: cat_dist[c] if c > 0 else -1), rank1)
    return cat_dist, proxy_rank, True


def _category_from_count(count):
    return {0: 0, 1: 0, 2: 1, 3: 3, 4: 7}.get(count, 0)


def flush_probability(column_cards, remaining_slots, pool_suit_counts, pool_size, future_draws):
    """P(this column reaches 5 of the same suit). The exact `remaining_slots`
    cards that end up here must ALL be the target suit -- modeled as a
    random sample of that size from the pool (using future_draws here
    instead gave a plain pair of Kings an absurd ~80% flush chance)."""
    if remaining_slots == 0 or not column_cards:
        counts = collections.Counter(s for r, s in column_cards)
        return 1.0 if (counts and max(counts.values()) == 5) else 0.0
    suit_counts = collections.Counter(s for r, s in column_cards)
    dom_suit, cur_count = suit_counts.most_common(1)[0]
    needed = 5 - len(column_cards)
    K = pool_suit_counts.get(dom_suit, 0)
    M = pool_size
    if needed > K or needed > M:
        return 0.0
    return hypergeom_pmf(K, M, needed, needed)


def column_category_distribution(column_cards, remaining_slots, pool_rank_counts, pool_suit_counts,
                                   pool_size, future_draws):
    """Combines rank-based development with flush-completion probability
    into one category distribution."""
    rank_dist, dom_rank, already_categories = column_count_distribution(column_cards, remaining_slots, pool_rank_counts, pool_size, future_draws)
    p_flush = flush_probability(column_cards, remaining_slots, pool_suit_counts, pool_size, future_draws)
    cat_dist = collections.defaultdict(float)
    for key, p in rank_dist.items():
        cat = key if already_categories else _category_from_count(key)
        cat_dist[cat] += p * (1 - p_flush)
    cat_dist[5] += p_flush
    total = sum(cat_dist.values())
    cat_dist = {k: v / total for k, v in cat_dist.items()} if total > 0 else {0: 1.0}
    return cat_dist, dom_rank


def _compare_category_distributions(my_dist, my_rank, opp_dist, opp_rank):
    """Core comparison logic, factored out so a caller that already has
    BOTH distributions in hand (e.g. a cached, unchanging opponent side)
    can skip recomputing either one."""
    p_win = 0.0
    p_tie = 0.0
    for my_cat, my_p in my_dist.items():
        for opp_cat, opp_p in opp_dist.items():
            joint = my_p * opp_p
            if my_cat > opp_cat: p_win += joint
            elif my_cat < opp_cat: pass
            else:
                if my_cat == 5:
                    p_tie += joint
                elif my_rank is not None and opp_rank is not None:
                    if my_rank > opp_rank: p_win += joint
                    elif my_rank < opp_rank: pass
                    else: p_tie += joint
                elif my_rank is not None: p_win += joint
                elif opp_rank is not None: pass
                else: p_tie += joint
    return p_win + 0.5 * p_tie


def column_win_probability(my_col, opp_col, pool_rank_counts, pool_size, my_future_draws, opp_future_draws,
                            pool_suit_counts=None):
    """P(I win this column by game end). Validated to within ~7 points
    across every category tier and hand-type tested this session."""
    my_slots = 5 - len(my_col)
    opp_slots = 5 - len(opp_col)
    if my_slots == 0 and opp_slots == 0:
        ra, rb = hand_rank(my_col), hand_rank(opp_col)
        return 1.0 if ra > rb else (0.0 if rb > ra else 0.5)
    suit_counts_to_use = pool_suit_counts if pool_suit_counts is not None else {}
    my_dist, my_rank = column_category_distribution(my_col, my_slots, pool_rank_counts, suit_counts_to_use, pool_size, my_future_draws)
    opp_dist, opp_rank = column_category_distribution(opp_col, opp_slots, pool_rank_counts, suit_counts_to_use, pool_size, opp_future_draws)
    return _compare_category_distributions(my_dist, my_rank, opp_dist, opp_rank)



def heuristic_action(hand, own_table, opp_table, burned):
    """The FAST heuristic (fit_score + category-only weak_bonus) -- this
    is the one used inside rollout(), where speed matters enormously
    (called thousands of times per search). See heuristic_action_winprob
    below for the win-probability-based alternative: it's ~53% better
    head-to-head as a standalone policy, but ~43x slower per call, which
    a direct MCTS-level A/B test showed makes it a NET NEGATIVE as a
    rollout policy under a fixed time budget -- far fewer completed
    rollouts costs more in search quality than the per-rollout accuracy
    gain returns. Keeping the fast version as the default here was a
    deliberate correction after that test, not an oversight."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    if plays_made < 4 and empties:
        rank_counts = collections.Counter(r for r, s in hand)
        trip_ranks = [r for r, cnt in rank_counts.items() if cnt >= 3]
        paired_ranks = sorted([r for r, cnt in rank_counts.items() if cnt == 2], reverse=True)
        non_trip_hand = [c for c in hand if c[0] not in trip_ranks]
        if trip_ranks and non_trip_hand:
            c = min(non_trip_hand, key=lambda c: c[0])
        elif paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
        else:
            c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])
    weak_bonus_by_slot = {i: -partial_strength(opp_table[i]) * 3 for i in open_slots}
    best = {}
    for c in hand:
        scored = []
        for i in open_slots:
            base = fit_score(c, own_table[i])
            scored.append((base + weak_bonus_by_slot[i], i))
        scored.sort(reverse=True)
        best[c] = scored[0]
    best_card = max(hand, key=lambda c: best[c][0]); val, slot = best[best_card]
    worst_card = min(hand, key=lambda c: best[c][0]); wval, _ = best[worst_card]
    if not burned and wval < 1.5 and val < 1.5:
        return ('burn', worst_card)
    return ('play', best_card, slot)


def winprob_general_phase(hand, own_table, opp_table, burned, open_slots):
    """The win-probability-based scoring logic, factored out so it can be
    called directly (bypassing the opening-phase check) -- needed because
    heuristic_action_winprob's own opening check would otherwise
    re-trigger the SAME naive fallback a caller might be trying to
    upgrade past, rather than ever reaching this more accurate logic."""
    rank_pool, suit_pool, pool_size = apparent_pool_with_suits(hand, own_table, opp_table, burned, None)
    my_draws = remaining_turns(own_table, burned)
    opp_draws = remaining_turns(opp_table, False)

    opp_dist_by_slot = {}
    for i in open_slots:
        opp_slots_i = 5 - len(opp_table[i])
        opp_dist_by_slot[i] = column_category_distribution(
            list(opp_table[i]), opp_slots_i, rank_pool, suit_pool, pool_size, opp_draws)

    def win_prob(my_col, i, my_draws_here):
        my_slots_i = 5 - len(my_col)
        if my_slots_i == 0 and (5 - len(opp_table[i])) == 0:
            ra, rb = hand_rank(my_col), hand_rank(opp_table[i])
            return 1.0 if ra > rb else (0.0 if rb > ra else 0.5)
        my_dist, my_rank = column_category_distribution(my_col, my_slots_i, rank_pool, suit_pool, pool_size, my_draws_here)
        opp_dist, opp_rank = opp_dist_by_slot[i]
        return _compare_category_distributions(my_dist, my_rank, opp_dist, opp_rank)

    current_probs = {i: win_prob(list(own_table[i]), i, my_draws) for i in open_slots}

    scores = {}
    for c in hand:
        for i in open_slots:
            hypothetical = list(own_table[i]) + [c]
            new_prob = win_prob(hypothetical, i, max(0, my_draws - 1))
            scores[(c, i)] = new_prob - current_probs[i]

    best_card, best_slot = max(((c, i) for c in hand for i in open_slots), key=lambda ci: scores[ci])
    best_delta = scores[(best_card, best_slot)]
    worst_card = min(hand, key=lambda c: max(scores[(c, i)] for i in open_slots))

    if not burned and best_delta < 0.01:
        return ('burn', worst_card)
    return ('play', best_card, best_slot)


def heuristic_action_winprob(hand, own_table, opp_table, burned):
    """Win-probability-based policy (see column_win_probability above).
    ~53% win rate head-to-head against heuristic_action as a STANDALONE
    policy (n=5500 across 3 batches, ~4.7 standard errors) -- but ~43x
    slower per call, which makes it a net negative as a rollout policy
    under a fixed search time budget (see heuristic_action's docstring).
    Good candidate for standalone play, or for root-level final move
    scoring where it's called far less often than inside rollout."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])  # forced (shouldn't occur in a legal state)
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    if plays_made < 4 and empties:                       # opening: seed every column first
        # Validated refinement #1: if the hand already contains a known
        # PAIR, play one card of that rank now instead of the
        # globally-lowest card -- there's no informational reason to defer
        # synergy you already know about.
        #
        # Validated refinement #2: TRIPS (or better) already in hand should
        # be HELD, not rushed out during the opening -- tested head-to-head
        # on identical deals: immediate deployment won 41.2%, holding until
        # opponent weakness is visible (falling through to the general
        # win-probability logic instead of the forced opening spread)
        # won 55.2%. A mere pair isn't strong enough to justify that same
        # patience (not much is lost either way), but a hand this strong is
        # worth deploying precisely rather than reflexively.
        rank_counts = collections.Counter(r for r, s in hand)
        trip_ranks = [r for r, cnt in rank_counts.items() if cnt >= 3]
        paired_ranks = sorted([r for r, cnt in rank_counts.items() if cnt == 2], reverse=True)
        non_trip_hand = [c for c in hand if c[0] not in trip_ranks]
        if trip_ranks and non_trip_hand:
            c = min(non_trip_hand, key=lambda c: c[0])
        elif paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
        else:
            c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])

    # General (post-opening) phase: score each candidate placement by its
    # MARGINAL contribution to that column's real win probability
    # (column_win_probability, validated to within ~7 points across every
    # category tier and hand-type tested this session), rather than the
    # older flat rank_matches constant + a crude opponent-category-only
    # weak_bonus. Validated via self-play against the old scoring: 53.2%
    # combined across 5,500 games (three independent batches, each
    # individually above 50%) -- ~4.7 standard errors, a real edge.
    return winprob_general_phase(hand, own_table, opp_table, burned, open_slots)

# ----------------------------------------------------------------------
# Fully-observed game state (one determinization)
# ----------------------------------------------------------------------
# State is IMMUTABLE and uses structural sharing: every step() only rebuilds
# the specific hand/column that actually changed and reuses the same tuple
# objects for everything untouched (the other player's whole table, the 3
# unaffected columns, etc). The deck is never copied at all -- it's a single
# shared tuple fixed at determinization time, with an integer "how many
# cards drawn so far" cursor advancing through it. This replaces the old
# approach of deep-copying the entire 40-card board on every single node in
# the search tree, which was the dominant cost per MCTS iteration.
@dataclass(frozen=True, slots=True)
class State:
    hands: tuple       # (handRoot(tuple), handOpp(tuple))
    tables: tuple       # (tableRoot(tuple of 4 tuples), tableOpp(tuple of 4 tuples))
    burned: tuple       # (boolRoot, boolOpp)
    deck_cards: tuple   # FULL shuffled unseen pile for this determinization (never mutated)
    deck_pos: int       # cards at index >= deck_pos are still undrawn
    to_move: int        # 0 = root player, 1 = opponent
    done: bool = False  # True once no player has a pending post-draw decision left

def legal_actions(state):
    """Slot choice is only meaningful if it can lead to a different outcome.
    Two of the mover's open slots are interchangeable -- and therefore
    collapsed into one representative action -- ONLY if BOTH sides' content
    at those slots currently match (column i is scored against the
    opponent's column i, so symmetry has to hold for the whole matchup, not
    just the mover's own cards). At the very start of the game this cuts
    the branching factor from slot choice by up to 4x with zero risk; it
    naturally stops applying the moment any column diverges from another."""
    p = state.to_move
    q = 1 - p
    hand = state.hands[p]
    tables_p = state.tables[p]
    tables_q = state.tables[q]
    open_slots = [i for i in range(4) if len(tables_p[i]) < 5]
    seen = set()
    dedup_slots = []
    for i in open_slots:
        sig = (tuple(sorted(tables_p[i])), tuple(sorted(tables_q[i])))
        if sig not in seen:
            seen.add(sig)
            dedup_slots.append(i)
    actions = []
    for c in hand:
        for s in dedup_slots:
            actions.append(('play', c, s))
    if not state.burned[p]:
        for c in hand:
            actions.append(('burn', c))
    return actions

def step(state, action):
    """Apply the current mover's play/burn (their hand was already at 6 --
    they drew before deciding, per the actual rule). If cards remain, deal
    the NEXT mover their pre-decision card so their hand is ready (6) when
    it becomes their turn. If the deck is empty, no one else can draw, so
    the game is over the moment this action is applied."""
    p = state.to_move
    q = 1 - p
    hands = list(state.hands)
    tables = state.tables
    burned = state.burned
    if action[0] == 'burn':
        c = action[1]
        hands[p] = tuple(x for x in state.hands[p] if x != c)
        burned = (True, burned[1]) if p == 0 else (burned[0], True)
    else:
        _, c, slot = action
        hands[p] = tuple(x for x in state.hands[p] if x != c)
        cols = list(state.tables[p])
        cols[slot] = state.tables[p][slot] + (c,)
        new_side = tuple(cols)
        tables = (new_side, tables[1]) if p == 0 else (tables[0], new_side)
    if state.deck_pos < len(state.deck_cards):
        drawn = state.deck_cards[state.deck_pos]
        hands[q] = state.hands[q] + (drawn,)
        return State(hands=tuple(hands), tables=tables, burned=burned,
                     deck_cards=state.deck_cards, deck_pos=state.deck_pos + 1,
                     to_move=q, done=False)
    else:
        hands[q] = state.hands[q]
        return State(hands=tuple(hands), tables=tables, burned=burned,
                     deck_cards=state.deck_cards, deck_pos=state.deck_pos,
                     to_move=q, done=True)

def is_terminal(state):
    return state.done

def evaluate_terminal(state, root_player):
    """+1 root wins majority, -1 opponent wins majority, 0 neither reaches 3."""
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

# ----------------------------------------------------------------------
# MCTS (UCT) on a single determinization
# ----------------------------------------------------------------------
def fit_score_hand_aware(card, slot_cards, hand_other_cards, rank_w=12, suit_w=1, straight_w=0.0, high_w=0.05, hand_synergy_w=2, junk_penalty_w=1.5):
    """Same as fit_score, but also credits a candidate card for matching
    OTHER cards still in hand (not yet played anywhere) -- not just what's
    already on the board. fit_score itself is deliberately left untouched
    (it's still used by heuristic_action, the rollout policy, where this
    same change was tested and found to REGRESS full MCTS-level play --
    see the session notes below action_priority).

    hand_synergy_w=2 (not the originally-tried 7): validated at the MCTS
    level that hand_synergy_w=7 combined with straight_w=0 was a CLEAR
    LOSS (2-8) despite EACH change individually testing well in isolation
    (hand-awareness alone: roughly neutral; straight_w=0 alone: a strong
    8-2 win) -- a genuine negative interaction between two individually-
    reasonable changes, not something either change's own isolated test
    would have revealed. Dropping to hand_synergy_w=2 resolved it (7-3,
    comparable to straight_w-removal alone) -- worth remembering as a
    general lesson: always test the ACTUAL combination being deployed,
    not just each change independently.

    straight_w defaults to 0.0 here (fit_score's default is 0.5) -- a
    user-reported failure mode confirmed via real screenshots: the
    nonzero straight_w rewards placing rank-ADJACENT (not matching) cards
    together, e.g. a 6 next to an existing 5, purely because they're
    numerically close -- even though this session extensively validated
    that pursuing straights is the single WORST strategy in this game
    (losing 84-99.6% of the time to even a simple response). Confirmed via
    direct calculation: this term contributed a smooth, monotonically
    decreasing bonus across every rank distance 1-4 (2.3 down to 0.95),
    actively outweighing unrelated candidates purely for being numerically
    close to a card that doesn't even match. Removing it alone validated
    as a strong MCTS-level win (8-2).

    junk_penalty_w: a SECOND, distinct user-reported failure mode --
    confirmed via real screenshots showing genuinely UNRELATED cards (not
    even rank-adjacent) piling into the same column, e.g. a 2 and a Queen
    together with nothing connecting them. Root cause: when a candidate
    card has no rank match anywhere, the score had NO mechanism to prefer
    an empty column over one already holding unrelated cards -- confirmed
    directly, a column with one junk card already in it scored EXACTLY
    the same as a totally empty column. This penalizes placing a
    non-matching card into a column that already holds unrelated cards
    (and doesn't yet have a pair of its own), proportional to how many
    such cards have already piled up -- makes an empty (or less-cluttered)
    column of my own the clear preference when no real synergy exists
    anywhere, instead of scattering junk arbitrarily. MCTS-level: 5-5,
    genuinely neutral (not the danger-sign pattern of the earlier bad
    interaction, which collapsed early and stayed bad) -- deployed on the
    strength of the confirmed, direct fix to observed behavior."""
    r, s = card
    n = len(slot_cards)
    if n >= 5: return -999
    rank_matches = sum(1 for rr, ss in slot_cards if rr == r)
    hand_matches = sum(1 for rr, ss in hand_other_cards if rr == r)
    if n == 0:
        return r * high_w + hand_matches * hand_synergy_w
    suit_matches = sum(1 for rr, ss in slot_cards if ss == s)
    mind = min(abs(r - rr) for rr, ss in slot_cards)
    score = rank_matches * rank_w + suit_matches * suit_w + hand_matches * hand_synergy_w
    if mind <= 4: score += (5 - mind) * straight_w
    score += r * high_w
    if rank_matches == 0:
        col_counts = {}
        for rr, ss in slot_cards: col_counts[rr] = col_counts.get(rr, 0) + 1
        col_has_pair = max(col_counts.values()) >= 2 if col_counts else False
        if not col_has_pair:
            score -= n * junk_penalty_w
    return score


def action_priority(action, hand, own_table, opp_table):
    """Heuristic score used ONLY to order which untried actions the tree
    expands first (progressive bias). This doesn't remove any move from
    consideration -- every legal action is still expanded eventually within
    a node -- it just spends the early iterations of a fixed budget on the
    branches most likely to matter, so the search goes deeper on the moves
    worth going deeper on instead of wasting rollouts on obviously bad ones.

    Uses fit_score_hand_aware (not the plain fit_score used by rollout) --
    this is a different, safer integration point for hand-awareness than
    rollout: every action still gets tried eventually regardless of initial
    order, so this doesn't carry the same rollout-value-calibration risk
    that caused a validated MCTS-level regression when hand-awareness was
    tried inside heuristic_action instead."""
    if action[0] == 'burn':
        c = action[1]
        hand_other = [card for card in hand if card != c]
        # A card that fits nowhere on our own board is a good burn candidate.
        best_fit = max((fit_score_hand_aware(c, own_table[i], hand_other) for i in range(4) if len(own_table[i]) < 5), default=0)
        return -best_fit
    _, c, slot = action
    hand_other = [card for card in hand if card != c]
    base = fit_score_hand_aware(c, own_table[slot], hand_other)
    weak_bonus = -partial_strength(opp_table[slot]) * 3
    return base + weak_bonus

class Node:
    __slots__ = ('state', 'parent', 'action', 'children', 'untried', 'visits', 'value', 'player')
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action
        self.children = []
        self.untried = legal_actions(state) if not is_terminal(state) else []
        p = state.to_move
        # sort ascending so pop() (which takes the LAST element) yields the
        # highest-priority action first -- promising moves get expanded,
        # and therefore searched deeper, before weaker ones.
        self.untried.sort(key=lambda a: action_priority(a, state.hands[p], state.tables[p], state.tables[1 - p]))
        self.visits = 0
        self.value = 0.0          # ALWAYS stored from root_player's perspective
        self.player = state.to_move

def uct_select(node, root_player, c=1.4):
    best, best_score = None, -1e18
    for ch in node.children:
        if ch.visits == 0:
            return ch
        q = ch.value / ch.visits
        q = q if node.player == root_player else -q   # negamax-style flip for opponent nodes
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

# ----------------------------------------------------------------------
# Determinization (sample the hidden information)
# ----------------------------------------------------------------------
def determinize(root_hand, root_table, opp_table, root_burned, root_burn_card, opp_burned, rng):
    assert len(root_hand) == 6, (
        f"root_hand must have exactly 6 cards (you draw BEFORE deciding, "
        f"so your hand is 6 at decision time) -- got {len(root_hand)}"
    )
    known = set(root_hand)
    for col in root_table: known.update(col)
    for col in opp_table: known.update(col)
    if root_burned and root_burn_card is not None:
        known.add(root_burn_card)
    unseen = [c for c in _FULL_DECK if c not in known]
    rng.shuffle(unseen)
    idx = 0
    opp_hand = tuple(unseen[idx:idx + 5]); idx += 5   # opponent is "resting" at 5 between their turns
    if opp_burned:
        idx += 1  # opponent's burn card: unknown identity, just remove it from the pool
    deck_cards = tuple(unseen[idx:])
    return State(
        hands=(tuple(root_hand), opp_hand),
        tables=(tuple(tuple(c) for c in root_table), tuple(tuple(c) for c in opp_table)),
        burned=(root_burned, opp_burned),
        deck_cards=deck_cards,
        deck_pos=0,
        to_move=0,
        done=False,
    )

# ----------------------------------------------------------------------
# Top-level PIMC solver: anytime, time-budgeted
# ----------------------------------------------------------------------
def solve(root_hand, root_table, opp_table, root_burned, root_burn_card, opp_burned,
          time_budget=8.0, iters_per_determinization=150, seed=None, verbose=False,
          significance_z=1.5):
    # Opening phase (still seeding empty columns, plays_made<4): this is
    # governed by an extensively validated hard rule (play a pair
    # immediately if available, hold trips, otherwise spread into an
    # empty column) that heuristic_action already applies correctly
    # inside rollout -- but that rule was NEVER enforced at this root
    # decision, only deep inside simulated games. Confirmed as a real bug
    # via a user-reported screenshot and direct reproduction: with two of
    # the bot's own columns still completely empty, full tree search
    # ranked BURNING above playing into the empty column (67.6% vs
    # 65.3%), even though heuristic_action called directly on the exact
    # same position correctly said to play into the empty column. The
    # tree searches over ALL legal actions including burn, and its
    # rollout-based value estimates are noisy enough this early (very
    # tight margins, large standard errors relative to the visit counts
    # -- see the session notes) to occasionally rank something else above
    # a move that's already known, with high confidence, to be correct.
    # Skipping search entirely for this decision is both safer (no noisy
    # ranking can override a known-correct move) and strictly faster.
    open_slots = [i for i in range(4) if len(root_table[i]) < 5]
    plays_made = sum(len(s) for s in root_table)
    empties = [i for i in range(4) if len(root_table[i]) == 0]
    if open_slots and plays_made < 4 and empties:
        opening_action = heuristic_action(root_hand, root_table, opp_table, root_burned)
        return [(opening_action, 1.0, 1)], 0, 0.0

    rng = random.Random(seed)
    action_stats = collections.defaultdict(lambda: [0, 0.0])  # visits, value(root-perspective)
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
        if verbose and dets % 10 == 0:
            print(f"  ...{dets} determinizations, {time.time()-start:.1f}s elapsed")
    ranked = []
    for a, (v, val) in action_stats.items():
        win_rate = (val / v + 1) / 2 if v > 0 else 0.5   # map [-1,1] avg -> [0,1] win share
        ranked.append((a, win_rate, v))
    ranked.sort(key=lambda x: x[1], reverse=True)
    elapsed = time.time() - start

    # Statistical-tie fallback: the opening-phase fix above handles the
    # cleanest case (moves 1-4), but the SAME underlying problem --
    # search's rollout-based win-rate estimates are noisy enough that the
    # ranking among genuinely close options is not reliable -- applies
    # anywhere two options are statistically indistinguishable, not just
    # in the opening. Confirmed directly: a search top-2 with win rates
    # 64.5%/64.0% on ~700 visits each has a combined standard error around
    # 2.6 points -- the 0.5-point gap between them is pure noise, and
    # trusting it as a real preference is exactly the mechanism that
    # ranked burning above an objectively correct move.
    #
    # Generalized fix: find the full group of actions statistically tied
    # with the top-ranked one (not just the top-2), and use
    # heuristic_action to break the tie ONLY among that group. An earlier
    # version of this fix blindly substituted heuristic_action's own
    # preferred move whenever the top-2 were tied, even if that move
    # wasn't part of the tied group at all -- caught directly: in one
    # test, heuristic_action's pick had a confidently-measured 15.8% win
    # rate (a 33-point gap from the top, nowhere near a tie), and the
    # buggy version promoted it anyway, discarding solid search evidence
    # in favor of a heuristic that search had already clearly overruled.
    # The fix must only ever break ties WITHIN the statistically
    # indistinguishable group -- never override a move search has
    # confidently ranked as worse.
    if len(ranked) >= 2:
        def _se(win_rate, visits):
            return math.sqrt(win_rate * (1 - win_rate) / visits) if visits > 0 else 1.0
        top_action, top_wr, top_v = ranked[0]
        se_top = _se(top_wr, top_v)
        _, second_wr, second_v = ranked[1]
        combined_se_top2 = math.sqrt(se_top ** 2 + _se(second_wr, second_v) ** 2)
        if (top_wr - second_wr) < significance_z * combined_se_top2:
            tied_indices = []
            for i, (a, wr, v) in enumerate(ranked):
                combined_se_i = math.sqrt(se_top ** 2 + _se(wr, v) ** 2)
                if (top_wr - wr) < significance_z * combined_se_i:
                    tied_indices.append(i)
                else:
                    break  # ranked is sorted descending -- first non-tied entry ends the group
            heuristic_choice = heuristic_action(root_hand, root_table, opp_table, root_burned)
            for i in tied_indices:
                if ranked[i][0] == heuristic_choice:
                    ranked.insert(0, ranked.pop(i))
                    break
            # if heuristic's choice isn't in the tied group, leave
            # search's own ranking as-is -- it already distinguished that
            # move as worse with real statistical confidence.

    return ranked, dets, elapsed

SUIT_CHR = 'shdc'  # spades, hearts, diamonds, clubs -> arbitrary fixed labels

def card_str(c):
    r, s = c
    rstr = {11: 'J', 12: 'Q', 13: 'K', 14: 'A'}.get(r, str(r))
    return f"{rstr}{SUIT_CHR[s]}"

def format_action(a):
    if a[0] == 'burn':
        return f"BURN {card_str(a[1])}"
    return f"PLAY {card_str(a[1])} -> column {a[2] + 1}"

# ----------------------------------------------------------------------
# Convenience entry point: describe a board with plain (rank, suit) tuples
# rank: 2-14 (11=J,12=Q,13=K,14=A), suit: 0=s,1=h,2=d,3=c
# ----------------------------------------------------------------------
def recommend_move(root_hand, root_table, opp_table, root_burned=False,
                    root_burn_card=None, opp_burned=False,
                    time_budget=8.0, iters_per_determinization=150, seed=None):
    """
    root_hand:   list of 6 (rank,suit) tuples -- your current hand, AFTER
                 this turn's draw (you draw before deciding what to play)
    root_table:  list of 4 lists -- your own 4 columns, cards already played
    opp_table:   list of 4 lists -- opponent's 4 columns (public info)
    root_burned: have YOU already used your burn? (you always know this)
    root_burn_card: which card you burned, if any (only used internally, never leaked)
    opp_burned:  has the OPPONENT already used their burn? (inferable from
                 turn counts: opp_turns_taken = sum(len(c) for c in opp_table) + (1 if burned)
                 vs. the known total number of turns they've had)
    Returns: (best_action, ranked_list, determinizations_run, seconds_elapsed)
    """
    ranked, dets, elapsed = solve(root_hand, root_table, opp_table,
                                   root_burned, root_burn_card, opp_burned,
                                   time_budget=time_budget,
                                   iters_per_determinization=iters_per_determinization,
                                   seed=seed)
    return ranked[0][0], ranked, dets, elapsed


if __name__ == '__main__':
    # Minimal worked example with a hand-specified board state.
    # root_hand has 6 cards: you've already drawn this turn.
    root_hand  = [(7,0), (11,0), (10,3), (9,0), (5,0), (6,1)]    # 7s Js 10c 9s 5s 6h
    root_table = [[(2,3),(13,3),(14,3),(14,0),(12,3)],           # full
                  [(4,1)],
                  [(5,1),(8,1),(8,2),(5,3),(12,1)],               # full
                  [(3,1)]]
    opp_table  = [[(3,0)],
                  [(3,2),(3,3),(13,2),(12,2)],
                  [(2,2),(2,1)],
                  [(7,3),(8,3),(10,2),(10,0),(6,2)]]              # full
    best, ranked, dets, elapsed = recommend_move(
        root_hand, root_table, opp_table,
        root_burned=False, opp_burned=False,
        time_budget=8.0, seed=1,
    )
    print(f"Searched {dets} determinizations in {elapsed:.1f}s")
    print("Top moves:")
    for a, wr, v in ranked[:5]:
        print(f"  {format_action(a):28s} win-rate~{wr:.3f} (n={v})")
    print("\nRecommended move:", format_action(best))
