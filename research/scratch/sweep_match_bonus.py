import random
import solver as S
import fast_heuristic as FH

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

def run(n, seed0=0):
    fast_wins = old_wins = 0
    for i in range(n):
        if i % 2 == 0:
            w = play_game(FH.heuristic_action_fast, S.heuristic_action, seed0+i)
            fw, ow = w[0], w[1]
        else:
            w = play_game(S.heuristic_action, FH.heuristic_action_fast, seed0+i)
            fw, ow = w[1], w[0]
        if fw > ow: fast_wins += 1
        elif ow > fw: old_wins += 1
    return fast_wins, old_wins

if __name__ == '__main__':
    import re
    src_path = 'fast_heuristic.py'
    with open(src_path) as f:
        original_src = f.read()
    for weight in [0.0, 0.15, 0.3, 0.6, 1.0]:
        new_src = re.sub(r'match_bonus = rank_matches \* [\d.]+', f'match_bonus = rank_matches * {weight}', original_src)
        with open(src_path, 'w') as f:
            f.write(new_src)
        import importlib
        importlib.reload(FH)
        fw, ow = run(800, seed0=600000)
        print(f'match_bonus weight={weight:.2f}: fast {fw} - old {ow}  ({100*fw/(fw+ow):.1f}%)')
    with open(src_path, 'w') as f:
        f.write(original_src)
