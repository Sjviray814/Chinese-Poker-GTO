import re
import importlib
import sweep_match_bonus as SW
import fast_heuristic as FH

src_path = 'fast_heuristic.py'
with open(src_path) as f:
    original_src = f.read()
for weight in [1.5, 2.0, 3.0, 5.0, 8.0]:
    new_src = re.sub(r'match_bonus = rank_matches \* [\d.]+', f'match_bonus = rank_matches * {weight}', original_src)
    with open(src_path, 'w') as f:
        f.write(new_src)
    importlib.reload(FH)
    fw, ow = SW.run(800, seed0=700000)
    print(f'match_bonus weight={weight:.2f}: fast {fw} - old {ow}  ({100*fw/(fw+ow):.1f}%)')
with open(src_path, 'w') as f:
    f.write(original_src)
