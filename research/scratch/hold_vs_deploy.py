import random, collections
import solver as S

def heuristic_immediate_deploy(hand, own_table, opp_table, burned):
    """Current behavior: known pair/trips gets played as soon as the
    opening spread reaches it."""
    return S.heuristic_action(hand, own_table, opp_table, burned)

def heuristic_delayed_deploy(hand, own_table, opp_table, burned):
    """If hand contains trips (3+ of a rank), DON'T commit them during the
    opening -- spread with other cards first, deploy the trips only once
    opponent's columns start revealing where they're weakest (after move 4)."""
    open_slots = [i for i in range(4) if len(own_table[i]) < 5]
    if not open_slots:
        return ('burn', hand[0])
    plays_made = sum(len(s) for s in own_table)
    empties = [i for i in range(4) if len(own_table[i]) == 0]
    rank_counts = collections.Counter(r for r, s in hand)
    trip_ranks = sorted([r for r, cnt in rank_counts.items() if cnt >= 3], reverse=True)

    if plays_made < 4 and empties:
        paired_ranks = sorted([r for r, cnt in rank_counts.items() if cnt >= 2 and cnt < 3], reverse=True)
        non_trip_hand = [c for c in hand if c[0] not in trip_ranks]
        if trip_ranks and non_trip_hand:
            # hold the trips; spread with a non-trip card instead
            c = min(non_trip_hand, key=lambda c: c[0])
            return ('play', c, empties[0])
        if paired_ranks:
            c = next(card for card in hand if card[0] == paired_ranks[0])
            return ('play', c, empties[0])
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

def force_trips_start(seed):
    """Deal a game where player 0 specifically starts with trips, to
    isolate exactly the scenario being tested (trips otherwise occurs in
    <5% of random hands, too rare to compare cleanly via unconstrained deals)."""
    rng = random.Random(seed)
    trip_rank = rng.choice(range(2,15))
    suits = [0,1,2,3]; rng.shuffle(suits)
    trips = [(trip_rank, suits[i]) for i in range(3)]
    deck = [c for c in S.make_deck() if c not in trips]
    rng.shuffle(deck)
    extra = [deck.pop() for _ in range(2)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0 = trips + extra
    rng.shuffle(hand0)
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    return S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                    deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)

def play_forced(strat0, strat1, seed):
    state = force_trips_start(seed)
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

if __name__ == '__main__':
    n = 6000
    immediate_wins = delayed_wins = ties = 0
    for i in range(n):
        w = play_forced(heuristic_immediate_deploy, heuristic_immediate_deploy, i)   # baseline for reference not used directly
    # proper A/B: player 0 always starts with trips, compare its OWN policy
    im_wins = de_wins = ties = 0
    for i in range(n):
        w = play_forced(heuristic_immediate_deploy, S.heuristic_action, 20000+i)
        if w[0] > w[1]: im_wins += 1
        elif w[1] > w[0]: pass
        else: ties += 1
    de_wins2 = 0; ties2 = 0
    for i in range(n):
        w = play_forced(heuristic_delayed_deploy, S.heuristic_action, 20000+i)  # SAME seeds -- same deals
        if w[0] > w[1]: de_wins2 += 1
        elif w[1] > w[0]: pass
        else: ties2 += 1
    print(f"Player 0 always starts with trips (random rank).")
    print(f"IMMEDIATE deploy (current rule) win rate: {100*im_wins/n:.2f}%  (ties: {ties})")
    print(f"DELAYED deploy (hold until move 5+) win rate: {100*de_wins2/n:.2f}%  (ties: {ties2})")
