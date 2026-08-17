import prob_fitscore
import fast_selfplay_v1 as bench

curves = {
    "original {0:0,1:0,2:1,3:3,4:7}": {0:0,1:0,2:1,3:3,4:7},
    "steeper {0:0,1:0,2:3,3:9,4:20}": {0:0,1:0,2:3,3:9,4:20},
    "much steeper {0:0,1:0,2:6,3:18,4:40}": {0:0,1:0,2:6,3:18,4:40},
    "linear-like {0:0,1:0,2:4,3:8,4:12}": {0:0,1:0,2:4,3:8,4:12},
}

for label, curve in curves.items():
    prob_fitscore.CATEGORY_VALUE = curve
    new_wins, old_wins, ties = bench.run_matchup(500, base_seed=700)
    print(f"{label}: new={new_wins} old={old_wins} ties={ties}  (new win rate {100*new_wins/500:.1f}%)")
