import re, importlib
import sweep_match_bonus as SW
import fast_heuristic as FH

src_path = 'fast_heuristic.py'
with open(src_path) as f:
    original_src = f.read()
for w in [0.5, 1.5, 3.0, 5.0]:
    new_src = re.sub(r'match_bonus = rank_matches \* 10\.0 \+ suit_matches \* [\d.]+',
                      f'match_bonus = rank_matches * 10.0 + suit_matches * {w}', original_src)
    with open(src_path, 'w') as f:
        f.write(new_src)
    importlib.reload(FH)
    fw, ow = SW.run(2500, seed0=9000000)
    print(f'suit weight={w}: fast {fw} - old {ow}  ({100*fw/(fw+ow):.1f}%)')
with open(src_path, 'w') as f:
    f.write(original_src)
