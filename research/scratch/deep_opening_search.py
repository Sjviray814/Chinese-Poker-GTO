import time
import solver as S

# Representative starting hand TYPES (rank, suit); suit 0=s,1=h,2=d,3=c
HAND_TYPES = {
    "no synergy (random spread)": [(3,0),(6,1),(9,2),(11,3),(13,0),(2,1)],
    "low pair (33)": [(3,0),(3,1),(7,2),(10,3),(12,0),(5,1)],
    "high pair (KK)": [(13,0),(13,1),(6,2),(9,3),(2,0),(11,1)],
    "mid pair (88)": [(8,0),(8,1),(3,2),(12,3),(5,0),(10,1)],
    "two pair (77,JJ)": [(7,0),(7,1),(11,2),(11,3),(4,0),(9,1)],
    "trips (999)": [(9,0),(9,1),(9,2),(4,3),(12,0),(6,1)],
    "suited-heavy (4 spades)": [(2,0),(6,0),(9,0),(13,0),(5,1),(11,2)],
    "connected run (5-6-7-8)": [(5,0),(6,1),(7,2),(8,3),(11,0),(2,1)],
}

BUDGET = 25.0   # deep, offline-style budget -- far more than any live turn gets
ITERS = 100

empty_table = [[],[],[],[]]

print(f"Deep search: {BUDGET}s budget per hand, {len(HAND_TYPES)} hand types\n")
results = {}
t0 = time.time()
for label, hand in HAND_TYPES.items():
    ranked, dets, elapsed = S.solve(
        hand, empty_table, empty_table, False, None, False,
        time_budget=BUDGET, iters_per_determinization=ITERS, seed=hash(label) % 100000)
    results[label] = ranked
    print(f"=== {label} ===  (dets={dets}, {elapsed:.1f}s)")
    for a, wr, n in ranked[:5]:
        print(f"   {S.format_action(a):26s}  win-rate~{wr:.3f}  (n={n})")
    print(f"   [total time so far: {time.time()-t0:.0f}s]\n")
