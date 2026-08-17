import random
import solver as S

def build_split_game(pair_a, pair_b, concentrate, seed):
    """concentrate=True: both pairs go into the SAME column (col0).
    concentrate=False: each pair goes into its OWN column (col0, col1)."""
    rng = random.Random(seed)
    reserved = set(pair_a) | set(pair_b)
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)
    our_extra = [deck.pop() for _ in range(1)]   # 2+2+1 = 5 starting cards
    opp_hand = [deck.pop() for _ in range(5)]
    hand0 = list(pair_a) + list(pair_b) + our_extra
    rng.shuffle(hand0)
    hand0.append(deck.pop())  # player 0 draws before first decision

    state = S.State(hands=(tuple(hand0), tuple(opp_hand)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)

    # force placement of the two designated pairs, then continue normally
    plan = list(pair_a) + list(pair_b)
    targets = [0,0,0,0] if concentrate else [0,0,1,1]
    burn_cards = [None, None]
    idx = 0
    while not S.is_terminal(state) and idx < len(plan):
        p = state.to_move
        if p == 0:
            card = plan[idx]; col = targets[idx]
            action = ('play', card, col)
            idx += 1
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if action[0] == 'burn': burn_cards[p] = action[1]
        state = S.step(state, action)

    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0] == 'burn': burn_cards[p] = a[1]
        state = S.step(state, a)
    return state

def run(label, pair_a, pair_b, concentrate, n, base_seed):
    wins = losses = ties = 0
    for i in range(n):
        state = build_split_game(pair_a, pair_b, concentrate, base_seed+i)
        w = sum(1 for i in range(4) if S.hand_rank(state.tables[0][i]) > S.hand_rank(state.tables[1][i]))
        w += 1 if S.hand_rank(state.hands[0]) > S.hand_rank(state.hands[1]) else 0
        l = sum(1 for i in range(4) if S.hand_rank(state.tables[1][i]) > S.hand_rank(state.tables[0][i]))
        l += 1 if S.hand_rank(state.hands[1]) > S.hand_rank(state.hands[0]) else 0
        if w > l: wins += 1
        elif l > w: losses += 1
        else: ties += 1
    print(f"{label:40s}: won {wins:5d}  lost {losses:5d}  tied {ties:3d}  (win rate {100*wins/n:.1f}%)")

if __name__ == '__main__':
    N = 4000
    PAIR_A = [(13,0),(13,1)]  # KK
    PAIR_B = [(7,2),(7,3)]    # 77
    print("Starting hand: KK + 77 (two separate pairs). Full-game win rate.\n")
    run("CONCENTRATE (both pairs -> col0)", PAIR_A, PAIR_B, True, N, base_seed=9001)
    run("SPLIT (KK -> col0, 77 -> col1)",   PAIR_A, PAIR_B, False, N, base_seed=9002)

def build_trips_split_game(trip_cards, split_2_1, seed):
    """split_2_1=False: all 3 trip cards go into col0 (concentrate).
    split_2_1=True: 2 go into col0 (a pair there), 1 goes into col1 alone."""
    rng = random.Random(seed)
    reserved = set(trip_cards)
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)
    our_extra = [deck.pop() for _ in range(2)]
    opp_hand = [deck.pop() for _ in range(5)]
    hand0 = list(trip_cards) + our_extra
    rng.shuffle(hand0)
    hand0.append(deck.pop())

    state = S.State(hands=(tuple(hand0), tuple(opp_hand)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    plan = list(trip_cards)
    targets = [0,0,0] if not split_2_1 else [0,0,1]
    burn_cards = [None, None]
    idx = 0
    while not S.is_terminal(state) and idx < len(plan):
        p = state.to_move
        if p == 0:
            action = ('play', plan[idx], targets[idx]); idx += 1
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if action[0]=='burn': burn_cards[p]=action[1]
        state = S.step(state, action)
    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0]=='burn': burn_cards[p]=a[1]
        state = S.step(state, a)
    return state

def run_trips(label, trip_cards, split_2_1, n, base_seed):
    wins = losses = ties = 0
    for i in range(n):
        state = build_trips_split_game(trip_cards, split_2_1, base_seed+i)
        w = sum(1 for i in range(4) if S.hand_rank(state.tables[0][i]) > S.hand_rank(state.tables[1][i]))
        w += 1 if S.hand_rank(state.hands[0]) > S.hand_rank(state.hands[1]) else 0
        l = sum(1 for i in range(4) if S.hand_rank(state.tables[1][i]) > S.hand_rank(state.tables[0][i]))
        l += 1 if S.hand_rank(state.hands[1]) > S.hand_rank(state.hands[0]) else 0
        if w > l: wins += 1
        elif l > w: losses += 1
        else: ties += 1
    print(f"{label:40s}: won {wins:5d}  lost {losses:5d}  tied {ties:3d}  (win rate {100*wins/n:.1f}%)")

if __name__ == '__main__' and True:
    N = 4000
    TRIPS = [(10,0),(10,1),(10,2)]
    print("\nStarting hand includes trips (10,10,10). Full-game win rate.\n")
    run_trips("CONCENTRATE (all 3 -> col0)", TRIPS, False, N, base_seed=9101)
    run_trips("SPLIT 2+1 (pair -> col0, 1 -> col1)", TRIPS, True, N, base_seed=9102)
