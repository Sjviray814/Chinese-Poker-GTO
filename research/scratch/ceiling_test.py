import solver as S

boards = {
    "mid-game (demo board)": dict(
        root_hand  = [(7,0), (11,0), (10,3), (9,0), (5,0), (6,1)],
        root_table = [[(2,3),(13,3),(14,3),(14,0),(12,3)], [(4,1)],
                      [(5,1),(8,1),(8,2),(5,3),(12,1)], [(3,1)]],
        opp_table  = [[(3,0)], [(3,2),(3,3),(13,2),(12,2)],
                      [(2,2),(2,1)], [(7,3),(8,3),(10,2),(10,0),(6,2)]],
    ),
    "early-game (empty columns)": dict(
        root_hand  = [(7,0), (11,0), (10,3), (9,0), (5,0), (6,1)],
        root_table = [[],[],[],[]],
        opp_table  = [[],[],[],[]],
    ),
}

BUDGETS = [0.5, 2.0, 8.0]

for name, b in boards.items():
    print(f"=== {name} ===")
    for budget in BUDGETS:
        ranked, dets, elapsed = S.solve(b["root_hand"], b["root_table"], b["opp_table"],
                                         False, None, False,
                                         time_budget=budget, iters_per_determinization=80, seed=7)
        top = ranked[0]
        print(f"  budget={budget:>4}s  dets={dets:4d}  top move: {S.format_action(top[0]):28s} "
              f"win-rate~{top[1]:.3f} (n={top[2]})   | 2nd: {S.format_action(ranked[1][0])} ({ranked[1][1]:.3f})")
    print()
