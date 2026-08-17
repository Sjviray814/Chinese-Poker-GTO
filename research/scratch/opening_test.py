import random, collections
import solver as S

def heuristic_action_smart_open(hand, own_table, opp_table, burned):
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]

    if plays_made < 4 and empties:
        # NEW: if hand already contains a known pair (or better), commit it
        # to a dedicated empty column immediately instead of blindly
        # spreading with the lowest card.
        rank_counts = collections.Counter(r for r, s in hand)
        paired_ranks = sorted([r for r, c in rank_counts.items() if c >= 2], reverse=True)
        if paired_ranks:
            target_rank = paired_ranks[0]
            # play one card of this rank into a fresh empty column
            card = next(c for c in hand if c[0] == target_rank)
            return ('play', card, empties[0])
        # no known synergy in hand -- fall back to the original rule
        c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])

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
    burn_cards=[None,None]
    strategies=[strat0,strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0]=='burn': burn_cards[p]=a[1]
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

def run_matchup(n, base_seed=0):
    new_wins = old_wins = ties = 0
    for i in range(n):
        seed = base_seed + i
        if i % 2 == 0:
            wins = play_game(heuristic_action_smart_open, S.heuristic_action, seed)
            nw, ow = wins[0], wins[1]
        else:
            wins = play_game(S.heuristic_action, heuristic_action_smart_open, seed)
            nw, ow = wins[1], wins[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
        else: ties += 1
    return new_wins, old_wins, ties

if __name__ == '__main__':
    n = 6000
    new_wins, old_wins, ties = run_matchup(n)
    print(f"SMART-OPEN (commit known pairs immediately) vs ORIGINAL (always spread lowest): {new_wins}-{old_wins}-{ties} over {n} games")
    print(f"Smart-open win rate: {100*new_wins/n:.2f}%")

def heuristic_action_smart_open_v2(hand, own_table, opp_table, burned):
    """More deliberate version: explicitly routes ALL copies of a paired
    rank to the SAME dedicated column during the opening, rather than
    playing one and leaving the second to be picked up later by chance."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]

    if plays_made < 4 and empties:
        rank_counts = collections.Counter(r for r, s in hand)
        paired_ranks = sorted([r for r, c in rank_counts.items() if c >= 2], reverse=True)
        # is any EXISTING (non-empty) own column already dedicated to a paired rank?
        for i in range(4):
            if own_table[i] and len(own_table[i]) < 5:
                col_rank = own_table[i][0][0]
                match = next((c for c in hand if c[0] == col_rank), None)
                if match:
                    return ('play', match, i)
        if paired_ranks:
            target_rank = paired_ranks[0]
            card = next(c for c in hand if c[0] == target_rank)
            return ('play', card, empties[0])
        c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])

    return S.heuristic_action(hand, own_table, opp_table, burned)

if __name__ == '__main__' and False:
    pass
