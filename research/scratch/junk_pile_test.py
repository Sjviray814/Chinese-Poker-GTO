import solver as S

def fit_score_junk_aware(card, slot_cards, hand_other_cards, rank_w=12, suit_w=1, straight_w=0.0, high_w=0.05, hand_synergy_w=2, junk_penalty_w=1.5):
    r, s = card
    n = len(slot_cards)
    if n >= 5: return -999
    rank_matches = sum(1 for rr, ss in slot_cards if rr == r)
    hand_matches = sum(1 for rr, ss in hand_other_cards if rr == r)
    if n == 0:
        return r * high_w + hand_matches * hand_synergy_w
    suit_matches = sum(1 for rr, ss in slot_cards if ss == s)
    mind = min(abs(r-rr) for rr, ss in slot_cards)
    score = rank_matches * rank_w + suit_matches * suit_w + hand_matches * hand_synergy_w
    if mind <= 4: score += (5 - mind) * straight_w
    score += r * high_w
    # NEW: if this card has no real synergy with the column (no rank
    # match), placing it into an already-populated column that ALSO has
    # no internal synergy compounds a wasted pile -- penalize proportional
    # to how many unrelated cards are already stacking up there.
    if rank_matches == 0:
        existing_ranks = set(rr for rr, ss in slot_cards)
        col_counts = {}
        for rr, ss in slot_cards: col_counts[rr] = col_counts.get(rr,0)+1
        col_has_pair = max(col_counts.values()) >= 2 if col_counts else False
        if not col_has_pair:
            score -= n * junk_penalty_w
    return score

def action_priority_junk_aware(action, hand, own_table, opp_table):
    if action[0] == 'burn':
        c = action[1]
        hand_other = [card for card in hand if card != c]
        best_fit = max((fit_score_junk_aware(c, own_table[i], hand_other) for i in range(4) if len(own_table[i]) < 5), default=0)
        return -best_fit
    _, c, slot = action
    hand_other = [card for card in hand if card != c]
    base = fit_score_junk_aware(c, own_table[slot], hand_other)
    weak_bonus = -S.partial_strength(opp_table[slot]) * 3
    return base + weak_bonus

if __name__ == '__main__':
    own = [[(2,1)], [], [(9,0)], [(11,2)]]
    opp = [[(5,0)], [(6,1)], [(3,2)], [(4,3)]]
    hand = [(12,0), (10,1), (7,3), (3,0), (8,1), (6,2)]
    for i in range(4):
        ap = action_priority_junk_aware(('play',(12,0),i), hand, own, opp)
        print(f'col{i} (currently {len(own[i])} of my cards): junk-aware priority = {ap:.2f}')
