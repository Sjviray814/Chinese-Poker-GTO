import random
import solver as S

def build_forced_game(our_cards, opp_cards, target_col, seed):
    """Generalized: our_cards and opp_cards can be any length 0-5.
    Forces those cards into target_col for each side (alternating with
    their normal turns), then continues with ordinary heuristic play."""
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
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)

    plan0, plan1 = list(our_cards), list(opp_cards)
    burn_cards = [None, None]
    while not S.is_terminal(state) and (plan0 or plan1):
        p = state.to_move
        plan = plan0 if p == 0 else plan1
        if plan:
            card = plan.pop(0)
            action = ('play', card, target_col)
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if action[0] == 'burn': burn_cards[p] = action[1]
        state = S.step(state, action)

    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0] == 'burn': burn_cards[p] = a[1]
        state = S.step(state, a)
    return state

def run_category(label, our_cards, opp_cards, n, base_seed, target_col=0):
    wins = losses = ties = 0
    for i in range(n):
        state = build_forced_game(our_cards, opp_cards, target_col, base_seed+i)
        ra, rb = S.hand_rank(state.tables[0][target_col]), S.hand_rank(state.tables[1][target_col])
        if ra > rb: wins += 1
        elif rb > ra: losses += 1
        else: ties += 1
    wr = 100*wins/n
    print(f"{label:46s}: won {wins:5d}  lost {losses:5d}  tied {ties:3d}   (win rate {wr:.1f}%)")
    return wr
