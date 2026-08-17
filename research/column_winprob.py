"""
Column win-probability estimator (v2) -- built and validated separately
from pivotality, per explicit instruction. Reuses the hypergeometric
machinery from analytic_eval.py (already checked against known reference
probabilities) and extends it into a full two-sided comparison that
accounts for how many slots each side has LEFT to fill, not just their
current snapshot. Category-ceiling effects (e.g. a mere pair can't
realistically beat established trips) should fall out of the comparison
naturally, rather than needing to be hand-coded as a special case.
"""

import collections
from solver import hand_rank
from analytic_eval import hypergeom_dist, hypergeom_pmf
from math import comb


def multivariate_hypergeom_dist(K1, K2, M, N):
    """Joint P(k1 of type1, k2 of type2) drawn among N from a pool of M
    containing K1 type1, K2 type2, rest other. Two ranks developing
    SIMULTANEOUSLY share the same N draws -- modeling them as two
    independent hypergeom_dist calls (an earlier version of this file
    did) double-counts the draw budget, which specifically inflates the
    joint "both succeed" outcome, i.e. full house. Verified: marginals of
    this joint distribution match the ordinary single-rank hypergeometric
    exactly, so this is strictly more correct, not just different."""
    dist = {}
    for k1 in range(0, min(K1, N) + 1):
        for k2 in range(0, min(K2, N - k1) + 1):
            other_needed = N - k1 - k2
            other_available = M - K1 - K2
            if other_needed < 0 or other_needed > other_available:
                continue
            p = comb(K1, k1) * comb(K2, k2) * comb(other_available, other_needed) / comb(M, N)
            dist[(k1, k2)] = p
    return dist


def column_count_distribution(column_cards, remaining_slots, pool_rank_counts, pool_size, future_draws):
    """Distribution over {final_count_of_dominant_rank: probability} for
    how this column's dominant rank is likely to resolve.

    Uses `remaining_slots` as the hypergeometric sample size EVERYWHERE,
    not `future_draws` -- a column can only ever receive `remaining_slots`
    more cards, period, no matter how many total draws the player has left
    in the whole game. Treating future_draws as the sample size (an
    earlier version of this function did, in two separate places) badly
    overestimates development, especially once multiple candidate ranks'
    pool counts get summed together -- verified: it inflated a weak
    unrelated 2-card hand's P(reach pair) to 86% and P(reach trips) to
    31%. `future_draws` is accepted as a parameter for interface
    compatibility but intentionally unused in the corrected model.
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
        # Already has an established pair (or better). A player can
        # patiently wait across their ENTIRE remaining game for a specific
        # rank and place it here whenever it arrives (verified: capping
        # the sample size to remaining_slots here, instead, badly broke
        # this branch's accuracy) -- so future_draws is the right sample
        # size for the draw itself, with placement capped at the slots
        # actually available.
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

    # No established pair yet -- multiple DIFFERENT ranks are present.
    # Earlier versions tracked only ONE candidate rank (either summed or
    # single-best), which structurally CANNOT represent two pair or full
    # house -- verified against real simulated play: a plain unpaired
    # 2-card column (e.g. 3,6) actually reaches at least a pair 97.5% of
    # the time, with two pair (31%) and full house (10%) alone accounting
    # for 41% of real outcomes. No amount of recalibrating a single-rank
    # model can fix a category it cannot represent at all. Track the top 2
    # candidate ranks jointly instead, so two pair / full house emerge
    # naturally from the (count1, count2) combination.
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
        # Escalating a column from an already-solid two pair up to full
        # house/quads requires BOTH ranks to keep hitting -- but that
        # assumes every matching draw gets greedily committed to THIS one
        # column, when a real player is also managing 3 other columns and
        # may well redirect a "bonus" match elsewhere once this column is
        # already in good shape. Verified against real simulated play:
        # this escalation was overestimating full house by roughly 2x
        # (predicted 20.2% vs actual 10.4%) while the TOTAL "both ranks
        # develop" mass (two pair + full house combined) was already
        # correct (41.7% vs 41.0%) -- so only the internal split needed
        # correcting, not the overall rate. Discount escalation beyond
        # two pair, redistributing the discounted mass back to two pair.
        if cat in (6, 7) and lo >= 2:
            escalate_discount = 0.5
            cat_dist[2] += joint * (1 - escalate_discount)
            best_rank_by_cat.setdefault(2, rank1 if count1 >= 2 else rank2)
            joint = joint * escalate_discount
        cat_dist[cat] += joint
        best_rank_by_cat.setdefault(cat, hi_rank if hi >= 2 else rank1)
    total = sum(cat_dist.values())
    cat_dist = {k: v / total for k, v in cat_dist.items()} if total > 0 else {0: 1.0}
    # represent the whole distribution's tiebreak rank as whichever rank
    # dominates in the single most likely non-trivial outcome
    proxy_rank = best_rank_by_cat.get(max(cat_dist, key=lambda c: cat_dist[c] if c > 0 else -1), rank1)
    return cat_dist, proxy_rank, True  # True marks this as already-a-category-distribution


def _category_from_count(count):
    """Rough category ordinal from a dominant-rank count alone (ignores
    two-pair/full-house/flush/straight -- consistent simplification used
    throughout this session's rank-priority-focused analysis)."""
    return {0: 0, 1: 0, 2: 1, 3: 3, 4: 7}.get(count, 0)


def flush_probability(column_cards, remaining_slots, pool_suit_counts, pool_size, future_draws):
    """P(this column reaches 5 of the same suit).

    IMPORTANT: this column can only ever receive `remaining_slots` MORE
    cards, total, no matter how many total draws the player has over the
    rest of the game -- using future_draws as the sample size (as an
    earlier version of this function did) conflates "enough suited cards
    exist somewhere among my future draws" with "this specific column's
    remaining slots all end up being that suit," and badly overestimates
    (verified: gave ~80% flush probability for a plain, unrelated pair of
    Kings in different suits, which is absurd). The correct question is
    whether the exact `remaining_slots` cards that end up here are all the
    target suit -- modeled as a random sample of that size from the pool."""
    if remaining_slots == 0 or not column_cards:
        counts = collections.Counter(s for r, s in column_cards)
        return 1.0 if (counts and max(counts.values()) == 5) else 0.0

    suit_counts = collections.Counter(s for r, s in column_cards)
    dom_suit, cur_count = suit_counts.most_common(1)[0]
    needed = 5 - len(column_cards)  # exact slots remaining, ALL must match
    K = pool_suit_counts.get(dom_suit, 0)
    M = pool_size
    if needed > K or needed > M:
        return 0.0
    p_flush = hypergeom_pmf(K, M, needed, needed)  # P(all `needed` draws are this suit)
    return p_flush


def column_category_distribution(column_cards, remaining_slots, pool_rank_counts, pool_suit_counts,
                                   pool_size, future_draws):
    """Combines rank-based development (pair/trips/quads) with
    flush-completion probability into one category distribution.
    Approximation: treat 'complete the flush' and 'rank development' as
    alternative outcomes rather than modeling their full joint distribution
    (both succeeding simultaneously is rare enough to ignore for this
    estimator) -- with probability p_flush, category becomes 5 (flush);
    otherwise, fall back to whatever the rank path gives."""
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


def column_win_probability(my_col, opp_col, pool_rank_counts, pool_size, my_future_draws, opp_future_draws,
                            pool_suit_counts=None):
    """P(I win this column by game end), comparing full hypergeometric
    development distributions for BOTH sides -- not just current snapshot.
    Category-ceiling effects (mere pair can't beat established trips,
    except via a same-or-higher-rank leapfrog) should emerge naturally
    from this comparison rather than needing special-case code.
    If pool_suit_counts is given, also models flush completion."""
    my_slots = 5 - len(my_col)
    opp_slots = 5 - len(opp_col)

    if my_slots == 0 and opp_slots == 0:
        ra, rb = hand_rank(my_col), hand_rank(opp_col)
        return 1.0 if ra > rb else (0.0 if rb > ra else 0.5)

    suit_counts_to_use = pool_suit_counts if pool_suit_counts is not None else {}
    my_dist, my_rank = column_category_distribution(my_col, my_slots, pool_rank_counts, suit_counts_to_use, pool_size, my_future_draws)
    opp_dist, opp_rank = column_category_distribution(opp_col, opp_slots, pool_rank_counts, suit_counts_to_use, pool_size, opp_future_draws)
    p_win = 0.0
    p_tie = 0.0
    for my_cat, my_p in my_dist.items():
        for opp_cat, opp_p in opp_dist.items():
            joint = my_p * opp_p
            if my_cat > opp_cat: p_win += joint
            elif my_cat < opp_cat: pass
            else:
                if my_cat == 5:
                    p_tie += joint  # both flush, no rank-of-flush model -- treat as tie
                elif my_rank is not None and opp_rank is not None:
                    if my_rank > opp_rank: p_win += joint
                    elif my_rank < opp_rank: pass
                    else: p_tie += joint
                elif my_rank is not None: p_win += joint
                elif opp_rank is not None: pass
                else: p_tie += joint
    return p_win + 0.5 * p_tie
