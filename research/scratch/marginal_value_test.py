import random
import solver as S
import multicolumn_harness as mch

def build_baseline_game(opp_columns, our_hand_extra_card, seed):
    """SAME opponent board, but our card is just part of our hand --
    NOT forced anywhere. Natural heuristic_action decides everything."""
    rng = random.Random(seed)
    opp_all = [c for cards in opp_columns.values() for c in cards]
    reserved = set(opp_all) | {our_hand_extra_card}
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)
    opp_extra = [deck.pop() for _ in range(max(0,5-len(opp_all)))]
    our_extra = [deck.pop() for _ in range(4)]
    hand0 = [our_hand_extra_card] + our_extra
    hand1 = (opp_all + opp_extra)[:5]
    rng.shuffle(hand0); rng.shuffle(hand1)
    hand0.append(deck.pop())
    state = S.State(hands=(tuple(hand0), tuple(hand1)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    plan1 = []
    for col, cards in opp_columns.items():
        for c in cards: plan1.append((c, col))
    rng.shuffle(plan1)
    while not S.is_terminal(state) and plan1:
        p = state.to_move
        if p == 1 and plan1:
            card, col = plan1.pop(0); action = ('play', card, col)
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, action)
    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, a)
    return state

def measure_column_winprob(build_fn, n, base_seed, col_index, **kwargs):
    wins = 0
    for i in range(n):
        state = build_fn(seed=base_seed+i, **kwargs)
        ra, rb = S.hand_rank(state.tables[0][col_index]), S.hand_rank(state.tables[1][col_index])
        if ra > rb: wins += 1
    return wins / n

if __name__ == '__main__':
    N = 3000
    OPP = {0: [(11,0),(11,1)], 1: [(3,2),(6,2)]}   # JJ (strong) in col0, weak suited-low in col1
    PAIR = [(8,0),(8,1)]

    print("Measuring MARGINAL win-probability change from forcing our pair (88) into each column\n")

    # baseline: card 8s is just part of hand, not forced -- measure natural P(win) per column
    # (use only ONE card of the pair as the 'single marginal card' for a clean single-card test)
    base_col0 = measure_column_winprob(build_baseline_game, N, 60001, col_index=0, opp_columns=OPP, our_hand_extra_card=(8,0))
    base_col1 = measure_column_winprob(build_baseline_game, N, 60002, col_index=1, opp_columns=OPP, our_hand_extra_card=(8,0))
    base_col2 = measure_column_winprob(build_baseline_game, N, 60003, col_index=2, opp_columns=OPP, our_hand_extra_card=(8,0))
    print(f"BASELINE (card not forced anywhere): P(win col0)={base_col0:.3f}  P(win col1)={base_col1:.3f}  P(win col2)={base_col2:.3f}")

    # forced: full pair placed in each candidate column
    def build_forced(seed, col):
        return mch.build_multicolumn_game(OPP, PAIR, col, seed)
    forced_col0 = measure_column_winprob(build_forced, N, 60011, col_index=0, col=0)
    forced_col1 = measure_column_winprob(build_forced, N, 60012, col_index=1, col=1)
    forced_col2 = measure_column_winprob(build_forced, N, 60013, col_index=2, col=2)
    print(f"FORCED (pair placed there):          P(win col0)={forced_col0:.3f}  P(win col1)={forced_col1:.3f}  P(win col2)={forced_col2:.3f}")

    print()
    print("MARGINAL delta (forced - baseline):")
    print(f"  col0 (contest strong): {forced_col0-base_col0:+.3f}")
    print(f"  col1 (attack weak):    {forced_col1-base_col1:+.3f}")
    print(f"  col2 (fresh):          {forced_col2-base_col2:+.3f}")
