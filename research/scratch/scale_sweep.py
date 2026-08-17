import importlib
import fast_selfplay_v1 as bench
import prob_fitscore

for scale in [3, 6, 12, 20, 30, 50]:
    prob_fitscore.EV_SCALE = scale
    new_wins, old_wins, ties = bench.run_matchup(600, base_seed=500)
    print(f"EV_SCALE={scale:3d}:  new={new_wins:3d}  old={old_wins:3d}  ties={ties}  (new win rate {100*new_wins/600:.1f}%)")
