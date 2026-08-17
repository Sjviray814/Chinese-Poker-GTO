import prob_fitscore
import fast_selfplay_v1 as bench

for scale in [4, 6, 8, 10, 12, 16, 20, 25]:
    prob_fitscore.EV_SCALE = scale
    new_wins, old_wins, ties = bench.run_matchup(1200, base_seed=3000)
    print(f"EV_SCALE={scale:3d}:  new={new_wins:4d}  old={old_wins:4d}  ties={ties}  (new win rate {100*new_wins/1200:.1f}%)")
