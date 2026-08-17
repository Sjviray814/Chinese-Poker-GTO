import random, collections
import solver as S

def fit_score_hand_aware(card, slot_cards, hand_other_cards, rank_w=12, suit_w=1, straight_w=0.5, high_w=0.05, hand_synergy_w=7):
    r, s = card
    n = len(slot_cards)
    if n >= 5: return -999
    if n == 0:
        # even for an empty column, credit potential future pairs in hand
        hand_matches = sum(1 for rr, ss in hand_other_cards if rr == r)
        return r * high_w + hand_matches * hand_synergy_w
    rank_matches = 0
    suit_matches = 0
    mind = 99
    for rr, ss in slot_cards:
        if rr == r: rank_matches += 1
        if ss == s: suit_matches += 1
        d = r - rr if r > rr else rr - r
        if d < mind: mind = d
    hand_matches = sum(1 for rr, ss in hand_other_cards if rr == r)
    score = rank_matches * rank_w + suit_matches * suit_w + hand_matches * hand_synergy_w
    if mind <= 4: score += (5 - mind) * straight_w
    score += r * high_w
    return score

def heuristic_action_hand_aware(hand, own_table, opp_table, burned):
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
    weak_bonus_by_slot = {i: -S.partial_strength(opp_table[i]) * 3 for i in open_slots}
    best = {}
    for c in hand:
        hand_other = [card for card in hand if card != c]
        scored = []
        for i in open_slots:
            base = fit_score_hand_aware(c, own_table[i], hand_other)
            scored.append((base + weak_bonus_by_slot[i], i))
        scored.sort(reverse=True)
        best[c] = scored[0]
    best_card = max(hand, key=lambda c: best[c][0]); val, slot = best[best_card]
    worst_card = min(hand, key=lambda c: best[c][0]); wval, _ = best[worst_card]
    if not burned and wval < 1.5 and val < 1.5:
        return ('burn', worst_card)
    return ('play', best_card, slot)
