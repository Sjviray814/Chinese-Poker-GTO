import random, time
import solver as S

def play_mcts_game(z0, z1, seed, time_budget=0.6):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    zs = [z0, z1]
    burn_cards = [None, None]
    while not S.is_terminal(state):
        p = state.to_move
        ranked, dets, elapsed = S.solve(list(state.hands[p]), [list(c) for c in state.tables[p]],
                                          [list(c) for c in state.tables[1-p]], state.burned[p],
                                          burn_cards[p], state.burned[1-p],
                                          time_budget=time_budget, iters_per_determinization=80,
                                          seed=rng.randint(0, 10**9), significance_z=zs[p])
        a = ranked[0][0] if ranked else S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0] == 'burn':
            burn_cards[p] = a[1]
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
    n = 10
    new_wins = old_wins = 0
    t0 = time.time()
    for i in range(n):
        if i % 2 == 0:
            w = play_mcts_game(2.0, 1.5, 300000+i)
            nw, ow = w[0], w[1]
        else:
            w = play_mcts_game(1.5, 2.0, 300000+i)
            nw, ow = w[1], w[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
        print(f'  game {i+1}/{n}: z=2.0 {new_wins} - z=1.5 {old_wins} ({time.time()-t0:.0f}s)')
    print(f'RESULT: z=2.0 vs z=1.5: {new_wins}-{old_wins}')
