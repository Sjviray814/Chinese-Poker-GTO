"""
Clean, current MCTS-level baseline benchmark -- run after the §8.6 fixes
(straight_w removal, junk-penalty, in both fit_score and
fit_score_hand_aware) to establish an up-to-date reference point. The
previous full benchmarks all predate these fixes.

Two questions:
1. How much does search actually add over the raw heuristic alone, under
   the CURRENT (fixed) scoring, at a realistic time budget?
2. How much does time budget itself matter (does the search meaningfully
   improve from 2s -> 4s -> 8s, informing what default the UI should use)?
"""
import random, time
import solver as S

def play_mcts_vs_heuristic(seed, time_budget, mcts_is_player0):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    burn_cards = [None, None]
    mcts_player = 0 if mcts_is_player0 else 1
    while not S.is_terminal(state):
        p = state.to_move
        if p == mcts_player:
            ranked, dets, elapsed = S.solve(list(state.hands[p]), [list(c) for c in state.tables[p]],
                                              [list(c) for c in state.tables[1-p]], state.burned[p],
                                              burn_cards[p], state.burned[1-p],
                                              time_budget=time_budget, iters_per_determinization=100,
                                              seed=rng.randint(0, 10**9))
            a = ranked[0][0] if ranked else S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        else:
            a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
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

def run_search_value_test(n, time_budget, base_seed):
    mcts_wins = heur_wins = 0
    t0 = time.time()
    for i in range(n):
        mcts_is_p0 = (i % 2 == 0)
        w = play_mcts_vs_heuristic(base_seed+i, time_budget, mcts_is_p0)
        mw, hw = (w[0], w[1]) if mcts_is_p0 else (w[1], w[0])
        if mw > hw: mcts_wins += 1
        elif hw > mw: heur_wins += 1
        print(f'  game {i+1}/{n}: MCTS {mcts_wins} - heuristic {heur_wins} ({time.time()-t0:.0f}s)')
    return mcts_wins, heur_wins

if __name__ == '__main__':
    print(f"=== Search value at {S.__name__} current scoring, budget=1.0s ===")
    mw, hw = run_search_value_test(10, 1.0, 5000000)
    print(f'RESULT: MCTS(1.0s) vs heuristic-alone: {mw}-{hw}\n')
