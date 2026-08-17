import random, time, collections
import solver as S
from microsim_v3 import mcts_search_v3

def solve_generic(search_fn, root_hand, root_table, opp_table, root_burned, root_burn_card, opp_burned,
                   time_budget, iters_per_det, seed, **kwargs):
    rng = random.Random(seed)
    action_stats = collections.defaultdict(lambda: [0, 0.0])
    start = time.time()
    dets = 0
    while time.time() - start < time_budget:
        det = S.determinize(root_hand, root_table, opp_table, root_burned, root_burn_card, opp_burned, rng)
        stats = search_fn(det, root_player=0, iterations=iters_per_det, **kwargs)
        for a, (v, val) in stats.items():
            action_stats[a][0] += v
            action_stats[a][1] += val
        dets += 1
    ranked = []
    for a, (v, val) in action_stats.items():
        wr = (val / v + 1) / 2 if v > 0 else 0.5
        ranked.append((a, wr, v))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked, dets

def v3_strategy(time_budget, iters_per_det, seed_base, leaf_samples=5):
    turn = {'n': 0}
    def strat(state, player, burn_cards):
        turn['n'] += 1
        ranked, dets = solve_generic(mcts_search_v3,
            list(state.hands[player]), [list(c) for c in state.tables[player]],
            [list(c) for c in state.tables[1-player]],
            state.burned[player], burn_cards[player], state.burned[1-player],
            time_budget, iters_per_det, seed_base*1000+turn['n'], leaf_samples=leaf_samples)
        return ranked[0][0]
    return strat

def rollout_strategy(time_budget, iters_per_det, seed_base):
    turn = {'n': 0}
    def strat(state, player, burn_cards):
        turn['n'] += 1
        ranked, dets, elapsed = S.solve(
            list(state.hands[player]), [list(c) for c in state.tables[player]],
            [list(c) for c in state.tables[1-player]],
            state.burned[player], burn_cards[player], state.burned[1-player],
            time_budget=time_budget, iters_per_determinization=iters_per_det, seed=seed_base*1000+turn['n'])
        return ranked[0][0]
    return strat

def play_game(strat0, strat1, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    empty_tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0), tuple(hand1)), tables=empty_tables,
                     burned=(False,False), deck_cards=tuple(deck), deck_pos=0,
                     to_move=0, done=False)
    burn_cards = [None, None]
    strategies = [strat0, strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](state, p, burn_cards)
        if a[0] == 'burn': burn_cards[p] = a[1]
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
    N_GAMES = 6
    TIME_BUDGET = 0.6
    ITERS = 50
    v3_wins = r_wins = ties = 0
    margins = []
    t0 = time.time()
    for g in range(N_GAMES):
        v3_strat = v3_strategy(TIME_BUDGET, ITERS, seed_base=11000+g, leaf_samples=5)
        r_strat = rollout_strategy(TIME_BUDGET, ITERS, seed_base=12000+g)
        if g % 2 == 0:
            wins = play_game(v3_strat, r_strat, seed=g)
            vw, rw = wins[0], wins[1]
        else:
            wins = play_game(r_strat, v3_strat, seed=g)
            vw, rw = wins[1], wins[0]
        if vw > rw: v3_wins += 1
        elif rw > vw: r_wins += 1
        else: ties += 1
        margins.append(vw - rw)
        print(f"game {g:2d}: V3 {vw} - {rw} ROLLOUT   [{time.time()-t0:.0f}s elapsed]")
    print()
    print(f"V3 (whole-board, opponent-aware, prob-informed) vs ROLLOUT record: {v3_wins}-{r_wins}-{ties} over {N_GAMES} games")
    print(f"Average column-margin for V3: {sum(margins)/len(margins):+.2f}")
