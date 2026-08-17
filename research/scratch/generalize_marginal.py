import random
import solver as S
import multicolumn_harness as mch
from marginal_value_test import build_baseline_game, measure_column_winprob

N = 2000

def test_board(label, opp_columns, our_resource, resource_card_for_baseline, seeds):
    print(f"=== {label} ===")
    results = []
    for col_idx in sorted(opp_columns.keys()) + [c for c in range(4) if c not in opp_columns]:
        base = measure_column_winprob(build_baseline_game, N, seeds[0]+col_idx*7,
                                       col_index=col_idx, opp_columns=opp_columns,
                                       our_hand_extra_card=resource_card_for_baseline)
        def build_forced(seed, col=col_idx):
            return mch.build_multicolumn_game(opp_columns, our_resource, col, seed)
        forced = measure_column_winprob(build_forced, N, seeds[1]+col_idx*7, col_index=col_idx, col=col_idx)
        delta = forced - base
        dist_from_half = abs(base - 0.5)
        print(f"  col{col_idx}: baseline={base:.3f}  forced={forced:.3f}  delta={delta:+.3f}  |dist from 0.5|={dist_from_half:.3f}")
        results.append((base, delta, dist_from_half))
    print()
    return results

all_results = []

# Board 1: full spread -- very weak, moderate, very strong, fresh
OPP1 = {0: [(2,1)], 1: [(9,0),(9,1)], 2: [(9,0),(9,1),(9,2)]}
all_results += test_board(
    "Board 1: weak-single(col0), pair(col1), trips(col2), fresh(col3)",
    OPP1, [(8,0),(8,1)], (8,0), seeds=(70000,71000))

# Board 2: different resource type (unrelated high cards instead of a pair), different opponent spread
OPP2 = {0: [(3,0),(6,0)], 1: [(11,0),(11,1),(13,2)], 2: [(9,0)]}
all_results += test_board(
    "Board 2: suited-low(col0), pair+kicker(col1), weak-single(col2), fresh(col3)",
    OPP2, [(14,1),(12,2)], (14,1), seeds=(72000,73000))

print("=== Summary across both boards: does distance-from-0.5 predict delta? ===")
all_results.sort(key=lambda r: r[2])
for base, delta, dist in all_results:
    print(f"  baseline={base:.3f}  |dist from 0.5|={dist:.3f}  ->  delta={delta:+.3f}")
