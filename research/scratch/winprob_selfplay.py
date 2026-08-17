import random, time
import solver as S
from winprob_heuristic import heuristic_action_winprob

def play_game(strat0, strat1, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    strategies=[strat0,strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](list(state.hands[p]), [list(c) for c in state.tables[p]], [list(c) for c in state.tables[1-p]], state.burned[p])
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

def run_matchup(n, base_seed=0):
    new_wins = old_wins = ties = 0
    t0 = time.time()
    for i in range(n):
        seed = base_seed + i
        if i % 2 == 0:
            wins = play_game(heuristic_action_winprob, S.heuristic_action, seed)
            nw, ow = wins[0], wins[1]
        else:
            wins = play_game(S.heuristic_action, heuristic_action_winprob, seed)
            nw, ow = wins[1], wins[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
        else: ties += 1
    elapsed = time.time()-t0
    print(f"WINPROB-BASED vs CURRENT: {new_wins}-{old_wins}-{ties} over {n} games ({100*new_wins/n:.1f}%)  [{elapsed:.0f}s, {n/elapsed:.1f} games/sec]")

if __name__ == '__main__':
    run_matchup(500)
