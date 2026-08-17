import random, time
import solver as S

def play_traced_game(seed, checkpoint_budget=0.4, iters_per_det=60):
    """Play a full game where BOTH sides use the MCTS solver's own top move
    each turn (so this is a 'well-played' trajectory, not a weak-heuristic
    one), recording P(player 0 wins | best play from here) at every turn."""
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
    trace = []  # (turn_number, p0_win_prob, mover, chosen_action_desc)
    turn = 0
    while not S.is_terminal(state):
        turn += 1
        p = state.to_move
        ranked, dets, elapsed = S.solve(
            list(state.hands[p]), [list(c) for c in state.tables[p]],
            [list(c) for c in state.tables[1-p]],
            state.burned[p], burn_cards[p], state.burned[1-p],
            time_budget=checkpoint_budget, iters_per_determinization=iters_per_det,
            seed=seed*10000+turn)
        best_action, best_wr, best_n = ranked[0]
        p0_win_prob = best_wr if p == 0 else (1 - best_wr)
        trace.append((turn, p0_win_prob, p, S.format_action(best_action), dets))
        if best_action[0] == 'burn':
            burn_cards[p] = best_action[1]
        state = S.step(state, best_action)
    # final actual outcome
    wins = [0, 0]
    for i in range(4):
        ra, rb = S.hand_rank(state.tables[0][i]), S.hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1
    ra, rb = S.hand_rank(state.hands[0]), S.hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1
    elif rb > ra: wins[1] += 1
    return trace, wins

if __name__ == '__main__':
    N_GAMES = 3
    t0 = time.time()
    all_traces = []
    for g in range(N_GAMES):
        trace, wins = play_traced_game(seed=100+g)
        all_traces.append((trace, wins))
        print(f"\n=== Game {g} (final score {wins[0]}-{wins[1]}) [{time.time()-t0:.0f}s elapsed] ===")
        prev = 0.5
        for turn, p0p, mover, action, dets in trace:
            swing = p0p - prev
            marker = '  <<<< BIG SWING' if abs(swing) > 0.15 else ''
            print(f"  turn {turn:2d} (P{mover} moved, dets={dets:3d}): P(P0 wins)={p0p:.3f}  (swing {swing:+.3f}){marker}")
            prev = p0p
    print(f"\nTotal time: {time.time()-t0:.0f}s")
