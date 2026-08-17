import random
import solver as S
import multicolumn_harness as mch

def build_pivotal_game(other_cols_setup, target_our_cards, target_col, seed):
    """other_cols_setup: dict {col: (our_cards, opp_cards)} -- forces the
    OTHER 3 columns to specific states (to create either an 'already
    decided' or 'genuinely 2-2 split' context), then forces target_our_cards
    into target_col, then plays out normally.

    With potentially MANY forced cards (more than fit in a 5-card starting
    hand), the excess must enter via early deck positions, not get silently
    dropped by truncating the hand -- otherwise the forcing loop tries to
    play a card that was never actually dealt, corrupting game state."""
    rng = random.Random(seed)
    our_plan = [(c, target_col) for c in target_our_cards]
    opp_plan = []
    for col, (our_c, opp_c) in other_cols_setup.items():
        our_plan += [(c, col) for c in our_c]
        opp_plan += [(c, col) for c in opp_c]
    rng.shuffle(opp_plan)

    our_committed = [c for c, _ in our_plan]
    opp_committed = [c for c, _ in opp_plan]
    reserved = set(our_committed) | set(opp_committed)
    filler = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(filler)

    hand0 = our_committed[:5]
    hand1 = opp_committed[:5]
    our_committed_excess = our_committed[5:]
    opp_committed_excess = opp_committed[5:]
    while len(hand0) < 5: hand0.append(filler.pop())
    while len(hand1) < 5: hand1.append(filler.pop())
    rng.shuffle(hand0); rng.shuffle(hand1)

    # excess forced cards go into the FRONT of the deck (interleaved with a
    # little filler) so they're drawn well before they're needed; the rest
    # of the deck is random filler.
    deck_front = []
    ex0, ex1 = list(our_committed_excess), list(opp_committed_excess)
    while ex0 or ex1:
        if ex0: deck_front.append(ex0.pop())
        if ex1: deck_front.append(ex1.pop())
    deck = list(reversed(deck_front)) + filler   # deck.pop() takes from the end -> front-of-queue cards drawn first
    hand0.append(deck.pop())

    state = S.State(hands=(tuple(hand0), tuple(hand1)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)

    p0, p1 = list(our_plan), list(opp_plan)
    while not S.is_terminal(state) and (p0 or p1):
        p = state.to_move
        plan = p0 if p == 0 else p1
        hand_now = state.hands[p]
        # play whichever planned card is actually available in hand right now
        idx = next((j for j, (c, col) in enumerate(plan) if c in hand_now), None)
        if idx is not None:
            card, col = plan.pop(idx)
            action = ('play', card, col)
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, action)
    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, a)
    return state

def run(label, other_setup, target_cards, target_col, n, base_seed):
    wins=losses=ties=0
    for i in range(n):
        state = build_pivotal_game(other_setup, target_cards, target_col, base_seed+i)
        w = mch.full_game_result(state)
        if w[0]>w[1]: wins+=1
        elif w[1]>w[0]: losses+=1
        else: ties+=1
    print(f"{label:60s}: FULL-GAME win rate {100*wins/n:.1f}%")

if __name__ == '__main__':
    N = 2500
    # ALREADY-SECURED context: we dominate all 3 OTHER columns heavily --
    # win guaranteed regardless of target_col's outcome.
    SECURED = {
        1: ([(13,0),(13,1),(13,2)], [(2,0),(5,1),(9,2)]),
        2: ([(12,0),(12,1),(12,2)], [(3,0),(4,1),(6,2)]),
        3: ([(11,0),(11,1),(11,2)], [(2,1),(3,2),(7,0)]),
    }
    # GENUINELY PIVOTAL context: 2 of the other columns are ours, 1 is
    # theirs -- so among the "other 4" (these 3 + the hidden hand), we're
    # sitting at 2 confirmed wins. If the natural hidden hand also goes our
    # way we already have 3 without needing target_col; if it doesn't, this
    # target column is exactly the 3rd win we need.
    PIVOTAL = {
        1: ([(13,0),(13,1),(13,2)], [(2,0),(5,1),(9,2)]),   # ours (secure)
        2: ([(12,0),(12,1),(12,2)], [(3,0),(4,1),(6,2)]),   # ours (secure)
        3: ([(2,1),(3,2),(7,0)], [(11,0),(11,1),(11,2)]),   # theirs (secure)
    }

    print("Same column-level move (weak -> stronger), different context:\n")
    run("ALREADY SECURED (win 3 of other 4 regardless)", SECURED, [(4,0),(4,1)], 0, N, 80001)
    run("GENUINELY PIVOTAL (need this to reach 3)", PIVOTAL, [(4,0),(4,1)], 0, N, 80002)
    print()
    print("Now the SAME target column WITHOUT the improvement (weaker filler instead):\n")
    run("ALREADY SECURED, weak filler in target col", SECURED, [(2,0),(3,1)], 0, N, 80003)
    run("GENUINELY PIVOTAL, weak filler in target col", PIVOTAL, [(2,0),(3,1)], 0, N, 80004)
