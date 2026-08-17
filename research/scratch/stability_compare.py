import time, random, collections
import solver as S
from analytic_eval import mcts_search_analytic

def solve_with(search_fn, root_hand, root_table, opp_table, time_budget, iters_per_det, seed):
    rng = random.Random(seed)
    action_stats = collections.defaultdict(lambda: [0, 0.0])
    start = time.time()
    dets = 0
    while time.time() - start < time_budget:
        det = S.determinize(root_hand, root_table, opp_table, False, None, False, rng)
        stats = search_fn(det, root_player=0, iterations=iters_per_det)
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

root_hand = [(7,0), (11,0), (10,3), (9,0), (5,0), (6,1)]
empty = [[],[],[],[]]

for label, search_fn in [("ROLLOUT-based", S.mcts_search), ("ANALYTIC", mcts_search_analytic)]:
    print(f"=== {label} ===")
    for budget in [0.5, 2.0, 8.0]:
        ranked, dets = solve_with(search_fn, root_hand, empty, empty, budget, 80, seed=7)
        top = ranked[0]
        print(f"  budget={budget:>4}s  dets={dets:4d}  top: {S.format_action(top[0]):24s} win-rate~{top[1]:.3f} (n={top[2]})   2nd: {S.format_action(ranked[1][0])} ({ranked[1][1]:.3f})")
    print()
