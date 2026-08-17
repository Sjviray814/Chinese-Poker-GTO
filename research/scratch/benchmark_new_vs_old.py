import random, time
import solver as NEW
import old_solver as OLD

def new_strategy(time_budget, iters_per_det, seed_base):
    turn = {'n': 0}
    def strat(state, player, burn_cards):
        turn['n'] += 1
        move_seed = seed_base * 1000 + turn['n']
        ranked, dets, elapsed = NEW.solve(
            list(state.hands[player]), [list(c) for c in state.tables[player]],
            [list(c) for c in state.tables[1-player]],
            state.burned[player], burn_cards[player], state.burned[1-player],
            time_budget=time_budget, iters_per_determinization=iters_per_det, seed=move_seed)
        return ranked[0][0]
    return strat

def old_strategy(time_budget, iters_per_det, seed_base):
    turn = {'n': 0}
    def strat(state, player, burn_cards):
        turn['n'] += 1
        move_seed = seed_base * 1000 + turn['n']
        ranked, dets, elapsed = OLD.solve(
            state.hands[player], state.tables[player], state.tables[1-player],
            state.burned[player], burn_cards[player], state.burned[1-player],
            time_budget=time_budget, iters_per_determinization=iters_per_det, seed=move_seed)
        return ranked[0][0]
    return strat

def play_game(strat0, strat1, seed):
    # Uses NEW's engine to actually run the game (rules are identical to OLD's;
    # only the search internals differ), converting types as needed per side.
    rng = random.Random(seed)
    deck = NEW.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    empty_tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = NEW.State(hands=(tuple(hand0), tuple(hand1)), tables=empty_tables,
                       burned=(False,False), deck_cards=tuple(deck), deck_pos=0,
                       to_move=0, done=False)
    burn_cards = [None, None]
    strategies = [strat0, strat1]
    while not NEW.is_terminal(state):
        p = state.to_move
        a = strategies[p](state, p, burn_cards)
        if a[0] == 'burn': burn_cards[p] = a[1]
        state = NEW.step(state, a)
    wins = [0, 0]; details = []
    for i in range(4):
        ra, rb = NEW.hand_rank(state.tables[0][i]), NEW.hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1; details.append('A')
        elif rb > ra: wins[1] += 1; details.append('B')
        else: details.append('T')
    ra, rb = NEW.hand_rank(state.hands[0]), NEW.hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1; details.append('A')
    elif rb > ra: wins[1] += 1; details.append('B')
    else: details.append('T')
    return wins, details

if __name__ == '__main__':
    N_GAMES = 6
    TIME_BUDGET = 0.8     # SAME wall-clock budget for both sides -- the whole point
    ITERS = 80
    new_wins = 0; old_wins = 0; ties = 0
    margins = []
    t0 = time.time()
    for g in range(N_GAMES):
        new_s = new_strategy(TIME_BUDGET, ITERS, seed_base=2000+g)
        old_s = old_strategy(TIME_BUDGET, ITERS, seed_base=3000+g)
        if g % 2 == 0:
            wins, details = play_game(new_s, old_s, seed=g)
            nw, ow = wins[0], wins[1]
        else:
            wins, details = play_game(old_s, new_s, seed=g)
            nw, ow = wins[1], wins[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
        else: ties += 1
        margins.append(nw - ow)
        print(f"game {g:2d}: NEW {nw} - {ow} OLD   ({''.join(details)})   [{time.time()-t0:.0f}s elapsed]")
    print()
    print(f"NEW (fast search) vs OLD (pre-optimization) record: {new_wins}-{old_wins}-{ties} over {N_GAMES} games")
    print(f"Average column-margin for NEW: {sum(margins)/len(margins):+.2f}")
    print(f"(both sides given the identical {TIME_BUDGET}s per move)")
