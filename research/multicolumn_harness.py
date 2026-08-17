import random
import solver as S

def build_multicolumn_game(opp_columns, our_commit, our_commit_col, seed):
    """opp_columns: dict {col_index: [cards]} -- opponent's existing board
    across MULTIPLE columns simultaneously.
    our_commit: list of cards we commit to our_commit_col (our one
    deliberate choice being tested); everything else plays out normally
    for both sides."""
    rng = random.Random(seed)
    opp_all_cards = [c for cards in opp_columns.values() for c in cards]
    reserved = set(opp_all_cards) | set(our_commit)
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)

    opp_extra_needed = max(0, 5 - len(opp_all_cards))
    our_extra_needed = max(0, 5 - len(our_commit))
    opp_extra = [deck.pop() for _ in range(opp_extra_needed)]
    our_extra = [deck.pop() for _ in range(our_extra_needed)]
    hand0 = (list(our_commit) + our_extra)[:5]
    hand1 = (list(opp_all_cards) + opp_extra)[:5]
    rng.shuffle(hand0); rng.shuffle(hand1)
    hand0.append(deck.pop())

    state = S.State(hands=(tuple(hand0), tuple(hand1)),
                     tables=((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple())),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)

    # build per-player "forced plan": (card, target_col) queues
    plan0 = [(c, our_commit_col) for c in our_commit]
    plan1 = []
    for col, cards in opp_columns.items():
        for c in cards:
            plan1.append((c, col))
    rng.shuffle(plan1)  # order among opponent's own forced cards doesn't matter much; keep it simple

    while not S.is_terminal(state) and (plan0 or plan1):
        p = state.to_move
        plan = plan0 if p == 0 else plan1
        if plan:
            card, col = plan.pop(0)
            action = ('play', card, col)
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, action)

    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        state = S.step(state, a)
    return state

def full_game_result(state):
    wins = [0, 0]
    for i in range(4):
        ra, rb = S.hand_rank(state.tables[0][i]), S.hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1
    ra, rb = S.hand_rank(state.hands[0]), S.hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1
    elif rb > ra: wins[1] += 1
    return wins

def run_allocation(label, opp_columns, our_commit, our_commit_col, n, base_seed):
    wins = losses = ties = 0
    for i in range(n):
        state = build_multicolumn_game(opp_columns, our_commit, our_commit_col, base_seed+i)
        w = full_game_result(state)
        if w[0] > w[1]: wins += 1
        elif w[1] > w[0]: losses += 1
        else: ties += 1
    print(f"{label:55s}: FULL-GAME win rate {100*wins/n:.1f}%  (won {wins} lost {losses} tied {ties})")
    return wins, losses, ties
