import random
import solver as S
import fast_heuristic as FH

def heuristic_opening_target(hand, own_table, opp_table, burned):
    """Same opening rules, but when choosing WHICH empty column to seed,
    prefer the one where the opponent's corresponding column already
    looks weakest (rather than just the first empty index)."""
    import collections
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
        # choose WHICH empty column: prefer the one where opponent looks weakest
        target_slot = min(empties, key=lambda i: FH.ARCHETYPE_TIER[FH.categorize_column(list(opp_table[i]))[0]])
        if trip_ranks and non_trip_hand:
            c = min(non_trip_hand, key=lambda c: c[0])
        elif paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
        else:
            c = min(hand, key=lambda c: c[0])
        return ('play', c, target_slot)
    return S.heuristic_action(hand, own_table, opp_table, burned)

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
            w = play_game(heuristic_opening_target, S.heuristic_action, i)
            nw, ow = w[0], w[1]
        else:
            w = play_game(S.heuristic_action, heuristic_opening_target, i)
            nw, ow = w[1], w[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
    print(f'OPPONENT-AWARE opening target vs CURRENT: {new_wins}-{old_wins} over {n} games ({100*new_wins/(new_wins+old_wins):.1f}%)')
