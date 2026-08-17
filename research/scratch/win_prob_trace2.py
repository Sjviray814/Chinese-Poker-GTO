import random, time
import solver as S

def determinize_flexible(fixed_hand, fixed_table, opp_table, fixed_burned, fixed_burn_card,
                          opp_burned, to_move, rng):
    """Like solver.determinize(), but doesn't assume fixed_player is about to
    move (their hand can be 5 or 6 cards) -- used for pure state-value
    estimation from a fixed perspective, regardless of whose turn it is."""
    known = set(fixed_hand)
    for col in fixed_table: known.update(col)
    for col in opp_table: known.update(col)
    if fixed_burned and fixed_burn_card is not None:
        known.add(fixed_burn_card)
    unseen = [c for c in S._FULL_DECK if c not in known]
    rng.shuffle(unseen)
    idx = 0
    opp_hand_size = 6 if to_move == 1 else 5
    opp_hand = unseen[idx:idx+opp_hand_size]; idx += opp_hand_size
    if opp_burned:
        idx += 1
    deck_cards = tuple(unseen[idx:])
    return S.State(
        hands=(tuple(fixed_hand), tuple(opp_hand)),
        tables=(tuple(tuple(c) for c in fixed_table), tuple(tuple(c) for c in opp_table)),
        burned=(fixed_burned, opp_burned),
        deck_cards=deck_cards, deck_pos=0, to_move=to_move, done=False,
    )

def estimate_state_value(fixed_hand, fixed_table, opp_table, fixed_burned, fixed_burn_card,
                          opp_burned, to_move, n_samples, seed):
    """Plain Monte Carlo: P(fixed player wins), no argmax/optimizer's-curse
    step anywhere -- just average outcomes under continued heuristic play."""
    rng = random.Random(seed)
    total = 0.0
    for _ in range(n_samples):
        det = determinize_flexible(fixed_hand, fixed_table, opp_table, fixed_burned,
                                    fixed_burn_card, opp_burned, to_move, rng)
        final = S.rollout(det)
        total += S.evaluate_terminal(final, root_player=0)
    avg = total / n_samples  # in [-1, 1]
    return (avg + 1) / 2      # rescale to [0, 1]

def play_traced_game_v2(seed, samples_per_checkpoint=400):
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
    trace = []
    turn = 0
    while not S.is_terminal(state):
        turn += 1
        # ALWAYS evaluate from Player 0's fixed perspective, regardless of whose turn it is
        p0_win_prob = estimate_state_value(
            list(state.hands[0]), [list(c) for c in state.tables[0]],
            [list(c) for c in state.tables[1]],
            state.burned[0], burn_cards[0], state.burned[1],
            state.to_move, samples_per_checkpoint, seed*10000+turn)
        trace.append((turn, p0_win_prob, state.to_move))
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
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
    return trace, wins

if __name__ == '__main__':
    N_GAMES = 3
    t0 = time.time()
    for g in range(N_GAMES):
        trace, wins = play_traced_game_v2(seed=200+g)
        print(f"\n=== Game {g} (final score {wins[0]}-{wins[1]}) [{time.time()-t0:.0f}s elapsed] ===")
        prev = 0.5
        for turn, p0p, mover in trace:
            swing = p0p - prev
            marker = '  <<<< swing' if abs(swing) > 0.15 else ''
            print(f"  turn {turn:2d} (P{mover}'s turn): P(P0 wins)={p0p:.3f}  (change {swing:+.3f}){marker}")
            prev = p0p
    print(f"\nTotal time: {time.time()-t0:.0f}s")
