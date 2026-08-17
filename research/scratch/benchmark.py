import random, time
import solver as S

def mcts_strategy(time_budget=1.0, iters_per_det=60, seed_base=None):
    turn_counter = {'n': 0}
    def strat(state, player, burn_cards):
        turn_counter['n'] += 1
        move_seed = None if seed_base is None else seed_base * 1000 + turn_counter['n']
        ranked, dets, elapsed = S.solve(
            state.hands[player], state.tables[player], state.tables[1-player],
            state.burned[player], burn_cards[player], state.burned[1-player],
            time_budget=time_budget, iters_per_determinization=iters_per_det, seed=move_seed)
        return ranked[0][0]
    return strat

def heuristic_strategy(state, player, burn_cards):
    return S.heuristic_action(state.hands[player], state.tables[player], state.tables[1-player], state.burned[player])

def play_game(strat0, strat1, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())  # player 0 draws before their first decision
    empty_tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0), tuple(hand1)), tables=empty_tables,
                     burned=(False,False), deck_cards=tuple(deck), deck_pos=0,
                     to_move=0, done=False)
    burn_cards=[None,None]
    strategies=[strat0, strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](state, p, burn_cards)
        if a[0]=='burn': burn_cards[p]=a[1]
        state = S.step(state, a)
    wins=[0,0]; details=[]
    for i in range(4):
        ra,rb = S.hand_rank(state.tables[0][i]), S.hand_rank(state.tables[1][i])
        if ra>rb: wins[0]+=1; details.append('A')
        elif rb>ra: wins[1]+=1; details.append('B')
        else: details.append('T')
    ra,rb = S.hand_rank(state.hands[0]), S.hand_rank(state.hands[1])
    if ra>rb: wins[0]+=1; details.append('A')
    elif rb>ra: wins[1]+=1; details.append('B')
    else: details.append('T')
    return wins, details

if __name__ == '__main__':
    N_GAMES = 12
    TIME_BUDGET = 1.0
    ITERS = 60
    mcts_wins = 0; heur_wins = 0; ties = 0
    margins = []
    t0 = time.time()
    for g in range(N_GAMES):
        mcts = mcts_strategy(time_budget=TIME_BUDGET, iters_per_det=ITERS, seed_base=1000+g)
        # alternate who plays first (player 0) to control for first-move advantage
        if g % 2 == 0:
            wins, details = play_game(mcts, heuristic_strategy, seed=g)
            mw, hw = wins[0], wins[1]
        else:
            wins, details = play_game(heuristic_strategy, mcts, seed=g)
            mw, hw = wins[1], wins[0]
        if mw > hw: mcts_wins += 1
        elif hw > mw: heur_wins += 1
        else: ties += 1
        margins.append(mw - hw)
        print(f"game {g:2d}: MCTS {mw} - {hw} Heuristic   ({''.join(details)})   [{time.time()-t0:.0f}s elapsed]")
    print()
    print(f"MCTS solver record: {mcts_wins}-{heur_wins}-{ties} over {N_GAMES} games")
    print(f"Average column-margin for MCTS: {sum(margins)/len(margins):+.2f}")
