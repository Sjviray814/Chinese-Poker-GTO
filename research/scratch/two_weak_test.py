import random
import solver as S
import multicolumn_harness as mch

def build_split_two_weak(opp_columns, pair_a, pair_b, col_a, col_b, seed):
    """Commit pair_a to col_a and pair_b to col_b (splitting across the
    two opponent-weak columns), or both pairs to the SAME column if
    col_a == col_b (concentrating)."""
    rng = random.Random(seed)
    opp_all = [c for cards in opp_columns.values() for c in cards]
    our_commit = list(pair_a) + list(pair_b)
    reserved = set(opp_all) | set(our_commit)
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)
    opp_extra = [deck.pop() for _ in range(max(0,5-len(opp_all)))]
    our_extra = [deck.pop() for _ in range(max(0,5-len(our_commit)))]
    hand0 = (our_commit + our_extra)[:5]
    hand1 = (opp_all + opp_extra)[:5]
    rng.shuffle(hand0); rng.shuffle(hand1)
    hand0.append(deck.pop())
    state = S.State(hands=(tuple(hand0), tuple(hand1)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    plan0 = [(c, col_a) for c in pair_a] + [(c, col_b) for c in pair_b]
    plan1 = []
    for col, cards in opp_columns.items():
        for c in cards: plan1.append((c, col))
    rng.shuffle(plan1)
    while not S.is_terminal(state) and (plan0 or plan1):
        p = state.to_move
        plan = plan0 if p==0 else plan1
        if plan:
            card, col = plan.pop(0); action = ('play', card, col)
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, action)
    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, a)
    return state

def run(label, opp_columns, pair_a, pair_b, col_a, col_b, n, base_seed):
    wins=losses=ties=0
    for i in range(n):
        state = build_split_two_weak(opp_columns, pair_a, pair_b, col_a, col_b, base_seed+i)
        w = mch.full_game_result(state)
        if w[0]>w[1]: wins+=1
        elif w[1]>w[0]: losses+=1
        else: ties+=1
    print(f"{label:55s}: FULL-GAME win rate {100*wins/n:.1f}%")

if __name__ == '__main__':
    N = 5000
    OPP = {0: [(3,0),(6,0)], 1: [(2,1),(5,1)]}  # both weak: suited-low in col0 AND col1
    PAIR_A = [(9,0),(9,1)]
    PAIR_B = [(10,2),(10,3)]
    print("Opponent shows WEAK suited-low in BOTH col0 and col1. We have two pairs (99, TT).\n")
    run("SPLIT (99->col0, TT->col1, one per weak column)", OPP, PAIR_A, PAIR_B, 0, 1, N, 50001)
    run("CONCENTRATE (both pairs -> col0 only)", OPP, PAIR_A, PAIR_B, 0, 0, N, 50002)
