import collections
import solver as S
from pivotal_estimator import estimate_win_prob, pivotality, partial_category

def heuristic_action_pivotal(hand, own_table, opp_table, burned):
    """Same opening rules as the current validated heuristic (spread first,
    pairs immediate, trips held). Only the GENERAL (post-opening) scoring
    changes: instead of flat rank_matches*12 + weak_bonus, score each
    candidate placement by how much it improves THIS column's estimated
    win probability, weighted by how pivotal this column currently is
    given the other three columns' estimated states."""
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

    # current estimated win prob for EACH of our 4 columns (post-opening)
    col_probs = [estimate_win_prob(own_table[i], opp_table[i]) for i in range(4)]
    # hidden hand: opponent's hand is unseen, so there's no opponent-side
    # comparison to make -- use our own hand's current category as a weak
    # signal (better than assuming a flat 0.5, though still crude), same
    # convention as elsewhere in this session.
    hidden_cat, _ = partial_category(hand)
    hidden_hand_prob = 0.5 + max(0, hidden_cat) * 0.05

    best_card, best_slot, best_value = None, None, -1e18
    for c in hand:
        for i in open_slots:
            hypothetical_col = own_table[i] + [c]
            new_prob = estimate_win_prob(hypothetical_col, opp_table[i])
            delta = new_prob - col_probs[i]
            # pivotality must be computed over the OTHER FOUR sub-hands
            # (the other 3 open columns AND the hidden hand) -- omitting
            # the hidden hand here was a real bug, not just a calibration
            # gap: it computes P(exactly 2 of 3) instead of P(exactly 2 of
            # 4), a different distribution with a different peak.
            others = [col_probs[j] for j in range(4) if j != i] + [hidden_hand_prob]
            weight = pivotality(others)
            value = delta * weight
            if value > best_value:
                best_value, best_card, best_slot = value, c, i

    worst_card = min(hand, key=lambda c: max(
        (estimate_win_prob(own_table[i] + [c], opp_table[i]) - col_probs[i]) *
        pivotality([col_probs[j] for j in range(4) if j != i] + [hidden_hand_prob])
        for i in open_slots))

    if not burned and best_value < 0.01:
        return ('burn', worst_card)
    return ('play', best_card, best_slot)
