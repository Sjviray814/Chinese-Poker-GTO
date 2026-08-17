import collections
from solver import fit_score, partial_strength
from prob_fitscore import apparent_pool_with_suits, remaining_turns
from column_winprob import column_win_probability


def heuristic_action_winprob(hand, own_table, opp_table, burned):
    """Same validated opening-phase logic as solver.heuristic_action
    (spread first, pairs immediate, trips held) -- only the GENERAL
    (post-opening) scoring changes: weak_bonus (a crude category-only
    proxy) is replaced with the real marginal win-probability delta from
    column_winprob.py, now validated to within ~7 points across every
    category tier and hand-type tested this session."""
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

    rank_pool, suit_pool, pool_size = apparent_pool_with_suits(hand, own_table, opp_table, burned, None)
    my_draws = remaining_turns(own_table, burned)
    # heuristic_action's signature doesn't currently expose opponent burn
    # status (weak_bonus never used it either) -- assume not-yet-burned as
    # a reasonable default, consistent with not regressing vs the baseline.
    opp_draws = remaining_turns(opp_table, False)

    current_probs = {i: column_win_probability(list(own_table[i]), list(opp_table[i]), rank_pool, pool_size,
                                                 my_draws, opp_draws, pool_suit_counts=suit_pool)
                      for i in open_slots}

    scores = {}
    for c in hand:
        for i in open_slots:
            hypothetical = list(own_table[i]) + [c]
            new_prob = column_win_probability(hypothetical, list(opp_table[i]), rank_pool, pool_size,
                                                max(0, my_draws - 1), opp_draws, pool_suit_counts=suit_pool)
            scores[(c, i)] = new_prob - current_probs[i]

    best_card, best_slot = max(((c, i) for c in hand for i in open_slots), key=lambda ci: scores[ci])
    best_delta = scores[(best_card, best_slot)]
    worst_card = min(hand, key=lambda c: max(scores[(c, i)] for i in open_slots))

    if not burned and best_delta < 0.01:
        return ('burn', worst_card)
    return ('play', best_card, best_slot)
