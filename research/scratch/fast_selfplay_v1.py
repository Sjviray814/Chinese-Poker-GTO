import random
import solver as S
from prob_fitscore import heuristic_action_v2

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
        a = strategies[p](state.hands[p], state.tables[p], state.tables[1-p], state.burned[p], burn_cards[p])
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

def old_strat(hand, own_table, opp_table, burned, own_burn_card):
    return S.heuristic_action(hand, own_table, opp_table, burned)

def new_strat(hand, own_table, opp_table, burned, own_burn_card):
    return heuristic_action_v2(hand, own_table, opp_table, burned, own_burn_card)

def run_matchup(n, base_seed=0):
    new_wins = old_wins = ties = 0
    for i in range(n):
        seed = base_seed + i
        if i % 2 == 0:
            wins = play_game(new_strat, old_strat, seed)
            nw, ow = wins[0], wins[1]
        else:
            wins = play_game(old_strat, new_strat, seed)
            nw, ow = wins[1], wins[0]
        if nw > ow: new_wins += 1
        elif ow > nw: old_wins += 1
        else: ties += 1
    return new_wins, old_wins, ties

if __name__ == '__main__':
    import time
    t0 = time.time()
    n = 2000
    new_wins, old_wins, ties = run_matchup(n)
    elapsed = time.time() - t0
    print(f"PROB-INFORMED (new) vs FLAT-CONSTANT (old): {new_wins}-{old_wins}-{ties} over {n} games")
    print(f"New win rate: {100*new_wins/n:.1f}%")
    print(f"({n} games in {elapsed:.1f}s -- {n/elapsed:.0f} games/sec)")
