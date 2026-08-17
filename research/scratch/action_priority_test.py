import solver as S

def fit_score_hand_aware(card, slot_cards, hand_other_cards, rank_w=12, suit_w=1, straight_w=0.5, high_w=0.05, hand_synergy_w=7):
    r, s = card
    n = len(slot_cards)
    if n >= 5: return -999
    if n == 0:
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

def action_priority_hand_aware(action, hand, own_table, opp_table):
    if action[0] == 'burn':
        c = action[1]
        hand_other = [card for card in hand if card != c]
        best_fit = max((fit_score_hand_aware(c, own_table[i], hand_other) for i in range(4) if len(own_table[i]) < 5), default=0)
        return -best_fit
    _, c, slot = action
    hand_other = [card for card in hand if card != c]
    base = fit_score_hand_aware(c, own_table[slot], hand_other)
    weak_bonus = -S.partial_strength(opp_table[slot]) * 3
    return base + weak_bonus
