import re, importlib
import sweep_match_bonus as SW
import fast_heuristic as FH

src_path = 'fast_heuristic.py'
with open(src_path) as f:
    original_src = f.read()
for scale in [0.3, 0.5, 0.7, 1.0, 1.3, 1.7, 2.0]:
    new_src = re.sub(r'TIER_SCALE = [\d.]+', f'TIER_SCALE = {scale}', original_src)
    with open(src_path, 'w') as f:
        f.write(new_src)
    importlib.reload(FH)
    fw, ow = SW.run(1200, seed0=1000000)
    print(f'TIER_SCALE={scale:.1f}: fast {fw} - old {ow}  ({100*fw/(fw+ow):.1f}%)')
with open(src_path, 'w') as f:
    f.write(original_src)
