import random, collections
import solver as S

def heuristic_delayed_pair(hand, own_table, opp_table, burned):
    """Same as current heuristic_action, EXCEPT move 1 always uses the
    lowest card (ignoring pairs); pair-priority only kicks in from move 2
    onward. Tests whether the pair needs to be literally first, or just
    somewhere in the opening window."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    if plays_made < 4 and empties:
        if plays_made == 0:
            c = min(hand, key=lambda c: c[0])
            return ('play', c, empties[0])
        rank_counts = collections.Counter(r for r, s in hand)
        paired_ranks = sorted([r for r, cnt in rank_counts.items() if cnt >= 2], reverse=True)
        if paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
        else:
            c = min(hand, key=lambda c: c[0])
        return ('play', c, empties[0])
    return S.heuristic_action(hand, own_table, opp_table, burned)

def heuristic_high_first_no_synergy(hand, own_table, opp_table, burned):
    """Same as current, EXCEPT when hand has no pair at all, play the
    HIGHEST card first instead of the lowest (matches the deep-search
    pattern seen on two separate no-synergy hands now)."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    if plays_made < 4 and empties:
        rank_counts = collections.Counter(r for r, s in hand)
        paired_ranks = sorted([r for r, cnt in rank_counts.items() if cnt >= 2], reverse=True)
        if paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
        else:
            c = max(hand, key=lambda c: c[0])   # HIGH instead of low
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

def run_matchup(stratA, stratB, n, base_seed=0):
    a_wins = b_wins = ties = 0
    for i in range(n):
        seed = base_seed + i
        if i % 2 == 0:
            wins = play_game(stratA, stratB, seed)
            aw, bw = wins[0], wins[1]
        else:
            wins = play_game(stratB, stratA, seed)
            aw, bw = wins[1], wins[0]
        if aw > bw: a_wins += 1
        elif bw > aw: b_wins += 1
        else: ties += 1
    return a_wins, b_wins, ties

if __name__ == '__main__':
    n = 10000
    aw, bw, t = run_matchup(heuristic_delayed_pair, S.heuristic_action, n, base_seed=100000)
    print(f"DELAYED-PAIR (move 2+) vs CURRENT (move 1): {aw}-{bw}-{t}  (delayed win rate {100*aw/n:.2f}%)")

    aw, bw, t = run_matchup(heuristic_high_first_no_synergy, S.heuristic_action, n, base_seed=200000)
    print(f"HIGH-FIRST (no synergy) vs CURRENT (low-first): {aw}-{bw}-{t}  (high-first win rate {100*aw/n:.2f}%)")
