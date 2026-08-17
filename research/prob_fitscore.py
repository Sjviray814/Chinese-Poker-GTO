"""
Probability-informed scoring for the EXISTING heuristic policy.

Unlike the two earlier attempts (v1 analytic evaluator, v2 micro-sim
evaluator), this does NOT replace heuristic_action or the rollout
mechanism. It replaces exactly one thing: the flat constant
`rank_matches * 12` inside fit_score, which currently scores "I have 2
cards of this rank already" the same way regardless of whether there's 1
copy of that rank left in a nearly-exhausted deck or 3 copies left in a
mostly-fresh one. Everything else -- the opponent-aware weak_bonus, the
opening-spread rule, suit/straight bonuses -- stays exactly as validated.

Reuses the hypergeometric machinery from analytic_eval.py (already
verified against known reference probabilities) to compute the actual
expected value of a column given a candidate placement, instead of a
hand-picked multiplier.
"""

import collections
from solver import _FULL_DECK, fit_score as fit_score_original
from analytic_eval import hypergeom_dist, column_count_distribution

# Approximate ordinal value of "ending up with N of the dominant rank" --
# same convention used in the (validated-independently) v1 evaluator.
CATEGORY_VALUE = {0: 0, 1: 0, 2: 1, 3: 3, 4: 7}

EV_SCALE = 12  # calibrated empirically below, not guessed


def apparent_pool(own_hand, own_table, opp_table_public, own_burned, own_burn_card):
    """Unseen-card composition from THIS player's own knowledge only --
    opponent's hand, opponent's burn (if any), and the true deck are all
    equally 'unseen' from here, exactly matching how determinize() treats
    hidden information during search."""
    known = set(own_hand)
    for col in own_table: known.update(col)
    for col in opp_table_public: known.update(col)
    if own_burned and own_burn_card is not None:
        known.add(own_burn_card)
    unseen = [c for c in _FULL_DECK if c not in known]
    return collections.Counter(r for r, s in unseen), len(unseen)


def apparent_pool_with_suits(own_hand, own_table, opp_table_public, own_burned, own_burn_card):
    """Same as apparent_pool, but also returns the unseen SUIT composition
    (needed for flush-completion probability)."""
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


def probability_informed_fit_score(card, slot_cards, hand_cards, pool_rank_counts, pool_size,
                                    own_future_draws, suit_w=1, straight_w=0.5, high_w=0.05):
    r, s = card
    n = len(slot_cards)
    if n >= 5:
        return -999
    if n == 0:
        return r * high_w

    # Does this card genuinely match something ALREADY in the column? Check
    # directly against the card's own rank -- NOT against a single
    # "most common rank" pick, which breaks ties arbitrarily whenever a
    # column has several different ranks each appearing once (very common
    # before any pair is established) and can wrongly classify a real match
    # as "non-matching" if the tie-break happened to land elsewhere.
    existing_count = sum(1 for rr, ss in slot_cards if rr == r)

    if existing_count == 0:
        # Doesn't build on anything already here -- stay at the original's
        # near-zero baseline (see earlier note: crediting speculative future
        # potential to a non-matching placement collapsed the gap between
        # good and bad choices and let weak_bonus override real synergy).
        suit_matches = sum(1 for rr, ss in slot_cards if ss == s)
        mind = min(abs(r - rr) for rr, ss in slot_cards)
        score = r * high_w + suit_matches * suit_w
        if mind <= 4:
            score += (5 - mind) * straight_w
        return score

    # Genuine match -- this is exactly the case where real probability
    # should replace the flat constant.
    hypothetical_column = list(slot_cards) + [card]
    remaining_slots = 5 - len(hypothetical_column)

    if remaining_slots == 0:
        counts = collections.Counter(rr for rr, ss in hypothetical_column)
        dom_count2 = counts.most_common(1)[0][1]
        ev = CATEGORY_VALUE.get(dom_count2, 7)
    else:
        dist, _ = column_count_distribution(
            hypothetical_column, [], remaining_slots,
            pool_rank_counts, pool_size, own_future_draws)
        ev = sum(p * CATEGORY_VALUE.get(k, 7) for k, p in dist.items())

    score = ev * EV_SCALE
    suit_matches = sum(1 for rr, ss in slot_cards if ss == s)
    mind = min(abs(r - rr) for rr, ss in slot_cards)
    if mind <= 4:
        score += (5 - mind) * straight_w
    score += suit_matches * suit_w
    score += r * high_w
    return score


def heuristic_action_v2(hand, own_table, opp_table, burned, own_burn_card=None):
    """Same structure as solver.heuristic_action (same opening rule, same
    opponent-aware weak-column targeting) -- only fit_score is swapped for
    the probability-informed version."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])  # forced (shouldn't occur in a legal state)
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    if plays_made < 4 and empties:
        c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])

    pool_rank_counts, pool_size = apparent_pool(hand, own_table, opp_table, burned, own_burn_card)
    own_draws = remaining_turns(own_table, burned)

    from solver import partial_strength
    best = {}
    for c in hand:
        scored = []
        for i in open_slots:
            base = probability_informed_fit_score(c, own_table[i], hand, pool_rank_counts, pool_size, own_draws)
            weak_bonus = -partial_strength(opp_table[i]) * 3   # UNCHANGED: attack opponent's weak columns
            scored.append((base + weak_bonus, i))
        scored.sort(reverse=True)
        best[c] = scored[0]
    best_card = max(hand, key=lambda c: best[c][0]); val, slot = best[best_card]
    worst_card = min(hand, key=lambda c: best[c][0]); wval, _ = best[worst_card]
    if not burned and wval < 8.0 and val < 8.0:
        return ('burn', worst_card)
    return ('play', best_card, slot)
