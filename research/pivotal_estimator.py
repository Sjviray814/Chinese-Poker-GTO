"""
Cheap, calibrated column win-probability estimator + pivotality weighting.

Two pieces:
1. estimate_win_prob(my_col, opp_col) -- fast category+rank-based estimate
   of P(I win this column by game end), calibrated against the extensive
   matchup simulations from this session (not simulated live -- a lookup/
   formula, meant to run inside the hot path of the heuristic).
2. pivotality(other_col_probs) -- P(exactly 2 of the other N win), the
   derivative of P(overall win>=3) with respect to the column in question.
"""
import itertools
from solver import hand_rank

def partial_category(cards):
    """Like solver.partial_strength but also exposes the dominant rank,
    needed for rank-aware estimation (not just category)."""
    if not cards:
        return -1, None
    cat, tiebreak = hand_rank(cards) if len(cards) >= 1 else (0, ())
    # hand_rank already handles partial hands (n<5) via its own branch
    dom_rank = tiebreak[0] if tiebreak else None
    return cat, dom_rank

# Calibration anchors from this session's simulations (category_diff -> win prob),
# roughly averaged across the many matchup tests run earlier.
CATEGORY_DIFF_TABLE = {
    -4: 0.02, -3: 0.05, -2: 0.15, -1: 0.30,
    0: 0.50,
    1: 0.74, 2: 0.85, 3: 0.93, 4: 0.98,
}
RANK_ADJUST_PER_STEP = 0.029  # calibrated from KK-vs-99 (rank+4 -> +12.9pts) and 44-vs-99 (rank-5 -> -13.2pts)

def estimate_win_prob(my_col, opp_col):
    my_cat, my_rank = partial_category(my_col)
    opp_cat, opp_rank = partial_category(opp_col)
    diff = max(-4, min(4, my_cat - opp_cat))
    base = CATEGORY_DIFF_TABLE[diff]
    if diff == 0 and my_rank is not None and opp_rank is not None:
        rank_diff = my_rank - opp_rank
        base += rank_diff * RANK_ADJUST_PER_STEP
    return max(0.01, min(0.99, base))

def pivotality(other_probs):
    """P(exactly 2 of the other N columns are wins) -- the marginal value
    multiplier for the column currently being evaluated. Exact via
    brute-force enumeration (N is always small, 3-4)."""
    n = len(other_probs)
    total = 0.0
    for combo in itertools.product([0, 1], repeat=n):
        if sum(combo) == 2:
            p = 1.0
            for c, prob in zip(combo, other_probs):
                p *= prob if c else (1 - prob)
            total += p
    return total
