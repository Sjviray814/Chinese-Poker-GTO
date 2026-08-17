import random, time
import solver as S

_ORIGINAL_AP = S.action_priority

def old_action_priority(action, hand, own_table, opp_table):
    """Reference: original action_priority (plain fit_score, straight_w=0.5, no hand-awareness)."""
    if action[0] == 'burn':
        c = action[1]
        best_fit = max((S.fit_score(c, own_table[i]) for i in range(4) if len(own_table[i]) < 5), default=0)
        return -best_fit
    _, c, slot = action
    base = S.fit_score(c, own_table[slot])
    weak_bonus = -S.partial_strength(opp_table[slot]) * 3
    return base + weak_bonus

def mcts_decide(hand, own_table, opp_table, own_burned, own_burn_card, opp_burned, ap_fn, time_budget, rng):
    S.action_priority = ap_fn
    try:
        ranked, dets, elapsed = S.solve(hand, own_table, opp_table, own_burned, own_burn_card, opp_burned,
                                          time_budget=time_budget, iters_per_determinization=60,
                                          seed=rng.randint(0, 10**9))
    finally:
        S.action_priority = _ORIGINAL_AP
    return ranked[0][0] if ranked else None

def play_mcts_game(ap0, ap1, seed, time_budget=0.4):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    aps = [ap0, ap1]
    burn_cards = [None, None]
    while not S.is_terminal(state):
        p = state.to_move
        a = mcts_decide(list(state.hands[p]), [list(c) for c in state.tables[p]], [list(c) for c in state.tables[1-p]],
                          state.burned[p], burn_cards[p], state.burned[1-p], aps[p], time_budget, rng)
        if a is None:
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

if __name__ == '__main__':
    n = 10
    new_wins = old_wins = 0
    t0 = time.time()
    for i in range(n):
        if i % 2 == 0:
            w = play_mcts_game(S.action_priority, old_action_priority, 990000+i)
            nw, ow = w[0], w[1]
        else:
            w = play_mcts_game(old_action_priority, S.action_priority, 990000+i)
            nw, ow = w[1], w[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
        print(f'  game {i+1}/{n}: running record {new_wins}-{old_wins} ({time.time()-t0:.0f}s)')
    print(f'MCTS-LEVEL (combined fix vs original): new {new_wins} - old {old_wins} over {n} games')
