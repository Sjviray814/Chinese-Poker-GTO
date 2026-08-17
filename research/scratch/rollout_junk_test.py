import random, collections
import solver as S

def fit_score_no_junk(card, slot_cards, rank_w=12, suit_w=1, straight_w=0.0, high_w=0.05, junk_penalty_w=1.5):
    r, s = card
    n = len(slot_cards)
    if n >= 5: return -999
    rank_matches = sum(1 for rr, ss in slot_cards if rr == r)
    if n == 0:
        return r * high_w
    suit_matches = sum(1 for rr, ss in slot_cards if ss == s)
    mind = min(abs(r-rr) for rr, ss in slot_cards)
    score = rank_matches*rank_w + suit_matches*suit_w
    if mind <= 4: score += (5-mind)*straight_w
    score += r*high_w
    if rank_matches == 0:
        col_counts = {}
        for rr, ss in slot_cards: col_counts[rr] = col_counts.get(rr,0)+1
        col_has_pair = max(col_counts.values()) >= 2 if col_counts else False
        if not col_has_pair:
            score -= n * junk_penalty_w
    return score

import collections

def heuristic_action_no_junk(hand, own_table, opp_table, burned):
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
        scored = []
        for i in open_slots:
            base = fit_score_no_junk(c, own_table[i])
            scored.append((base + weak_bonus_by_slot[i], i))
        scored.sort(reverse=True)
        best[c] = scored[0]
    best_card = max(hand, key=lambda c: best[c][0]); val, slot = best[best_card]
    worst_card = min(hand, key=lambda c: best[c][0]); wval, _ = best[worst_card]
    if not burned and wval < 1.5 and val < 1.5:
        return ('burn', worst_card)
    return ('play', best_card, slot)

def play_game(strat0, strat1, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    strategies=[strat0,strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](list(state.hands[p]), [list(c) for c in state.tables[p]], [list(c) for c in state.tables[1-p]], state.burned[p])
        state = S.step(state, a)
    wins = [0, 0]
    for i in range(4):
        ra, rb = S.hand_rank(state.tables[0][i]), S.hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1
    ra, rb = S.hand_rank(state.hands[0]), S.hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1
    elif rb > ra: wins[1] += 1
    return wins

if __name__ == '__main__':
    n = 4000
    new_wins = old_wins = 0
    for i in range(n):
        if i % 2 == 0:
            w = play_game(heuristic_action_no_junk, S.heuristic_action, i)
            nw, ow = w[0], w[1]
        else:
            w = play_game(S.heuristic_action, heuristic_action_no_junk, i)
            nw, ow = w[1], w[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
    print(f'NO-JUNK ROLLOUT vs ORIGINAL (raw self-play): {new_wins}-{old_wins} ({100*new_wins/(new_wins+old_wins):.1f}%)')
