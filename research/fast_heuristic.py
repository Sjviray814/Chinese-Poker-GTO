"""
Fast, table-based column-priority heuristic. Not a probability calculation
at all -- a categorization + lookup, informed by the extensive validated
matchup data gathered earlier this session (matchup_harness.py results).
Goal: capture almost all of the win-probability estimator's decision
quality at close to the ORIGINAL heuristic's speed, by replacing
per-candidate combinatorics with O(1) table lookups and cheap pool-count
checks (not full hypergeometric distributions).
"""
import collections

# Archetype ordinal tiers, matching the validated category-hierarchy
# finding (category beats rank almost everywhere) -- higher = stronger.
# Fractional values let same-tier archetypes (e.g. a pair with vs without
# a kicker) sit at meaningfully different strength without a full new tier.
TIER_SCALE = 1.5  # relative weight of the archetype-tier/weak-attack signal vs match_bonus -- swept empirically (peak ~1.3-2.0 at n=1200, ~50% parity vs original)

ARCHETYPE_TIER = {
    'empty': 0.0,
    'weak_unrelated': 0.5,
    'straight_draw': 0.3,   # validated WORSE than weak_unrelated (loses to a mere pair 84-99.6% of the time)
    'flush_draw': 0.6,      # validated weak, but not as bad as a straight draw
    'single_low': 0.4,
    'single_high': 1.0,
    'pair': 3.0,
    'pair_kicker': 3.3,     # validated: a kicker meaningfully strengthens a same-rank pair matchup
    'two_pair': 4.0,
    'trips': 5.0,
    'full_house': 6.0,
    'quads': 7.0,
}

def categorize_column(cards):
    """Return (archetype, primary_rank, secondary_rank) for a column's
    current cards. Deliberately avoids collections.Counter -- profiling
    showed Counter + .most_common() (which internally uses heapq.nlargest,
    a partial-sort) was the dominant cost, applied to columns that hold at
    most 5 cards. This is the exact same class of fix already validated
    earlier this session (removing Counter from partial_strength gave a
    3.5x speedup there) -- just not applied here the first time around."""
    if not cards:
        return ('empty', None, None)
    if len(cards) == 1:
        r = cards[0][0]
        return ('single_high' if r >= 9 else 'single_low', r, None)

    rank_counts = {}
    suit_counts = {}
    for r, s in cards:
        rank_counts[r] = rank_counts.get(r, 0) + 1
        suit_counts[s] = suit_counts.get(s, 0) + 1

    top_rank, top_count = None, 0
    second_rank, second_count = None, 0
    for r, cnt in rank_counts.items():
        if cnt > top_count or (cnt == top_count and (top_rank is None or r > top_rank)):
            second_rank, second_count = top_rank, top_count
            top_rank, top_count = r, cnt
        elif cnt > second_count or (cnt == second_count and (second_rank is None or r > second_rank)):
            second_rank, second_count = r, cnt

    if top_count >= 4:
        return ('quads', top_rank, None)
    if top_count == 3 and second_count >= 2:
        return ('full_house', top_rank, second_rank)
    if top_count == 3:
        return ('trips', top_rank, None)
    if top_count == 2 and second_count == 2:
        return ('two_pair', max(top_rank, second_rank), min(top_rank, second_rank))
    if top_count == 2:
        has_kicker = len(cards) > 2
        return ('pair_kicker' if has_kicker else 'pair', top_rank, None)

    max_suit_count = max(suit_counts.values())
    if max_suit_count >= 3:
        return ('flush_draw', max(r for r, s in cards), None)
    ranks_sorted = sorted(rank_counts.keys())
    if len(cards) >= 3 and ranks_sorted[-1] - ranks_sorted[0] <= 4:
        return ('straight_draw', max(r for r, s in cards), None)
    return ('weak_unrelated', max(r for r, s in cards), None)


def fast_score(hypothetical_col, opp_categorized, pool_rank_counts, candidate_card, prior_col):
    """Score a hypothetical column state against the opponent's ALREADY
    CATEGORIZED state in that column (opp_categorized = (arch, r1, r2)).
    Taking the pre-categorized tuple instead of the raw opp_col lets the
    caller categorize the opponent's side ONCE per slot instead of once
    per candidate card -- the opponent's column doesn't change based on
    which of our own cards we're considering, so recomputing it per
    candidate (as an earlier version did, 48 categorize_column calls per
    decision instead of the ~28 actually needed) was pure waste.

    Also includes an explicit reward for the candidate card MATCHING the
    column's existing rank(s) -- the original fit_score's rank_matches
    term was the dominant signal there for good reason (extending an
    existing grouping is how you reliably reach trips/quads at all), and
    dropping it entirely in this redesign was a real bug: verified via
    category-distribution diagnostics, full house dropped by nearly half
    and quads to a third versus the original heuristic, because nothing
    was explicitly rewarding "this card completes what's already here"
    over "this card starts something new elsewhere.\""""
    my_arch, my_r1, my_r2 = categorize_column(hypothetical_col)
    opp_arch, opp_r1, opp_r2 = opp_categorized
    my_tier = ARCHETYPE_TIER[my_arch]
    opp_tier = ARCHETYPE_TIER[opp_arch]

    rank_matches = sum(1 for r, s in prior_col if r == candidate_card[0])
    suit_matches = sum(1 for r, s in prior_col if s == candidate_card[1])
    match_bonus = rank_matches * 10.0 + suit_matches * 0.5

    if opp_arch == 'quads' and my_arch != 'quads':
        if my_arch == 'trips' and my_r1 is not None and opp_r1 is not None and my_r1 > opp_r1:
            if pool_rank_counts.get(my_r1, 0) >= 1:
                return 5.1 + match_bonus
        return -100.0

    if abs(my_tier - opp_tier) > 1e-9:
        return (my_tier - opp_tier) * TIER_SCALE + match_bonus

    # Same tier -- validated rank-based tiebreak, calibrated PER TIER
    # against tier-crossing itself as the common reference scale (1.0 =
    # one tier-crossing's decisiveness, anchored at ~74% from "any pair
    # beats weak"/~24 points above a 50% coin flip). Anchors: pair vs pair
    # (KK vs 99, rank_diff=4 -> 62.9%, 13 points -> ~0.135/step in tier
    # units) vs trips vs trips (QQQ beating 999, rank_diff=3 -> 73.8%,
    # 23.8 points -> ~0.33/step) -- nearly 2.5x steeper. Caught via a
    # direct sanity check: an earlier flat rate scored a trips-beats-trips
    # advantage (a near-win, ~74%) as barely better than a single high
    # card facing an empty column (a near coin flip) -- backwards, because
    # it wasn't expressed on the same decisiveness scale as tier-crossing.
    PER_RANK_STEP = {'pair': 0.135, 'pair_kicker': 0.135, 'two_pair': 0.20,
                      'trips': 0.33, 'full_house': 0.35}
    if my_r1 is not None and opp_r1 is not None:
        rank_diff = my_r1 - opp_r1
        step = PER_RANK_STEP.get(my_arch, 0.135)
        score = rank_diff * step
        if my_r2 is not None and opp_r2 is not None and rank_diff == 0:
            score += (my_r2 - opp_r2) * step * 0.3
        return score * TIER_SCALE + match_bonus
    return match_bonus


def heuristic_action_fast(hand, own_table, opp_table, burned):
    """Fast table-based policy: no probability calculation, just
    categorization + lookup + a cheap availability check. Same validated
    opening-phase rules (spread first, pairs immediate, trips held)."""
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

    known = set(hand)
    for col in own_table: known.update(col)
    for col in opp_table: known.update(col)
    pool_rank_counts = collections.Counter()
    for r in range(2, 15):
        pool_rank_counts[r] = 4
    for (r, s) in known:
        pool_rank_counts[r] -= 1

    scores = {}
    opp_categorized_by_slot = {i: categorize_column(list(opp_table[i])) for i in open_slots}
    for c in hand:
        for i in open_slots:
            prior_col = list(own_table[i])
            hypothetical = prior_col + [c]
            scores[(c, i)] = fast_score(hypothetical, opp_categorized_by_slot[i], pool_rank_counts, c, prior_col)

    best_card, best_slot = max(((c, i) for c in hand for i in open_slots), key=lambda ci: scores[ci])
    best_val = scores[(best_card, best_slot)]
    worst_card = min(hand, key=lambda c: max(scores[(c, i)] for i in open_slots))

    if not burned and best_val < 0.1:
        return ('burn', worst_card)
    return ('play', best_card, best_slot)


def heuristic_action_hybrid(hand, own_table, opp_table, burned):
    """Same as heuristic_action_fast, EXCEPT: when the opening-phase
    logic would otherwise fall through to a blind 'lowest card' default
    (no pair or trips in hand to prioritize), use the slower but more
    accurate exact win-probability heuristic instead. This sub-case is
    rare -- a handful of times per real game, and only briefly at the
    START of each rollout, not thousands of times throughout it -- so
    the extra cost is easily affordable exactly where it matters most
    for opening play."""
    import solver as S
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
            return ('play', c, empties[0])
        elif paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
            return ('play', c, empties[0])
        else:
            # no clear synergy signal -- worth the extra computation here.
            # Calls the general-phase scoring DIRECTLY (not the whole
            # heuristic_action_winprob function) -- that function has its
            # own opening check, which would otherwise just re-trigger
            # this exact same fallback instead of ever reaching the more
            # accurate logic.
            return S.winprob_general_phase(hand, own_table, opp_table, burned, open_slots)
    return heuristic_action_fast(hand, own_table, opp_table, burned)
