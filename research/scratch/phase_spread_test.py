import random
import solver as S

def simulate_to_depth(depth, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    empty = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0), tuple(hand1)), tables=empty,
                     burned=(False,False), deck_cards=tuple(deck), deck_pos=0,
                     to_move=0, done=False)
    burn_cards = [None, None]
    for _ in range(depth):
        if S.is_terminal(state):
            break
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0] == 'burn':
            burn_cards[p] = a[1]
        state = S.step(state, a)
    return state, burn_cards

DEPTHS = [
    (0,  "opening (0 turns played)"),
    (8,  "early (8 turns played)"),
    (18, "mid (18 turns played)"),
    (28, "mid-late (28 turns played)"),
    (38, "late (38 turns played)"),
]
BUDGET = 3.0
ITERS = 80
SEEDS = [11, 22]

print(f"{'phase':32s} {'#candidates':>11s} {'top1':>7s} {'top2':>7s} {'gap(1-2)':>9s} {'top5':>7s} {'gap(1-5)':>9s}")
for depth, label in DEPTHS:
    gaps12 = []; gaps15 = []; ncands = []
    for seed in SEEDS:
        state, burn_cards = simulate_to_depth(depth, seed)
        if S.is_terminal(state):
            continue
        root = state.to_move
        ranked, dets, elapsed = S.solve(
            list(state.hands[root]), [list(c) for c in state.tables[root]],
            [list(c) for c in state.tables[1-root]],
            state.burned[root], burn_cards[root], state.burned[1-root],
            time_budget=BUDGET, iters_per_determinization=ITERS, seed=seed*100)
        top1 = ranked[0][1]
        top2 = ranked[1][1] if len(ranked) > 1 else top1
        top5 = ranked[min(4, len(ranked)-1)][1]
        gaps12.append(top1 - top2)
        gaps15.append(top1 - top5)
        ncands.append(len(ranked))
        print(f"  [{label:30s}] seed={seed}: #cand={len(ranked):3d}  top1={top1:.3f}  top2={top2:.3f}  gap12={top1-top2:.3f}  top5={top5:.3f}  gap15={top1-top5:.3f}")
    if gaps12:
        avg_n = sum(ncands)/len(ncands)
        avg12 = sum(gaps12)/len(gaps12)
        avg15 = sum(gaps15)/len(gaps15)
        print(f"{label:32s} {avg_n:11.1f} {'':7s} {'':7s} {avg12:9.3f} {'':7s} {avg15:9.3f}")
    print()
