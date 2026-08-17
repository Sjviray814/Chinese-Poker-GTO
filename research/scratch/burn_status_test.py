import random
import solver as S

def build_forced_game_burn(our_cards, opp_cards, target_col, our_burned, opp_burned, seed):
    rng = random.Random(seed)
    reserved = set(our_cards) | set(opp_cards)
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)
    our_extra_needed = max(0, 5 - len(our_cards))
    opp_extra_needed = max(0, 5 - len(opp_cards))
    our_extra = [deck.pop() for _ in range(our_extra_needed)]
    opp_extra = [deck.pop() for _ in range(opp_extra_needed)]
    hand0 = (list(our_cards) + our_extra)[:5]
    hand1 = (list(opp_cards) + opp_extra)[:5]
    rng.shuffle(hand0); rng.shuffle(hand1)
    hand0.append(deck.pop())

    state = S.State(hands=(tuple(hand0), tuple(hand1)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(our_burned, opp_burned), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    plan0, plan1 = list(our_cards), list(opp_cards)
    while not S.is_terminal(state) and (plan0 or plan1):
        p = state.to_move
        plan = plan0 if p == 0 else plan1
        if plan:
            action = ('play', plan.pop(0), target_col)
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, action)
    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, a)
    return state

def run(label, our_cards, opp_cards, our_burned, opp_burned, n, base_seed, target_col=0):
    wins = losses = ties = 0
    for i in range(n):
        state = build_forced_game_burn(our_cards, opp_cards, target_col, our_burned, opp_burned, base_seed+i)
        ra, rb = S.hand_rank(state.tables[0][target_col]), S.hand_rank(state.tables[1][target_col])
        if ra > rb: wins += 1
        elif rb > ra: losses += 1
        else: ties += 1
    print(f"{label:55s}: win rate {100*wins/n:.1f}%")

if __name__ == '__main__':
    N = 3000
    # close matchup (our lower pair vs their higher pair) -- does burn status shift it?
    OUR = [(9,0),(9,1)]
    OPP = [(11,0),(11,1)]
    print("Close matchup: our 99 vs opp JJ, testing burn status effects\n")
    run("Neither burned yet", OUR, OPP, False, False, N, 7001)
    run("WE have already burned, opp has not", OUR, OPP, True, False, N, 7002)
    run("Opp has already burned, we have not", OUR, OPP, False, True, N, 7003)
    run("Both already burned", OUR, OPP, True, True, N, 7004)
