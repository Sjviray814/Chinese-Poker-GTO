import random
import solver as S
from luck_vs_skill import random_strategy, play_game

def mcts_strategy(time_budget, iters_per_det, seed_base):
    turn = {'n': 0}
    def strat(state, player, burn_cards):
        turn['n'] += 1
        move_seed = seed_base * 1000 + turn['n']
        ranked, dets, elapsed = S.solve(
            list(state.hands[player]), [list(c) for c in state.tables[player]],
            [list(c) for c in state.tables[1-player]],
            state.burned[player], burn_cards[player], state.burned[1-player],
            time_budget=time_budget, iters_per_determinization=iters_per_det, seed=move_seed)
        return ranked[0][0]
    return strat

N = 10
wins_mcts = 0; wins_random = 0
margins = []
for g in range(N):
    mcts = mcts_strategy(0.8, 80, seed_base=5000+g)
    if g % 2 == 0:
        wins = play_game(mcts, random_strategy, seed=g)
        wm, wr = wins[0], wins[1]
    else:
        wins = play_game(random_strategy, mcts, seed=g)
        wm, wr = wins[1], wins[0]
    if wm > wr: wins_mcts += 1
    elif wr > wm: wins_random += 1
    margins.append((wm, wr))
    print(f"game {g}: MCTS {wm} - {wr} Random")
print()
print(f"MCTS vs Random: {wins_mcts}-{wins_random} over {N} games  ({100*wins_mcts/N:.0f}% for MCTS)")
