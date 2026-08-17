import random
import solver as S

def build_forced_game(opp_pair_cards, our_cards, target_col, seed):
    """Deal a random game where opp_pair_cards end up committed to
    target_col for the opponent, and our_cards end up committed to
    target_col for us -- both as if they were each player's opening moves
    into that column -- then continue via normal heuristic play."""
    rng = random.Random(seed)
    reserved = set(opp_pair_cards) | set(our_cards)
    deck = [c for c in S.make_deck() if c not in reserved]
    rng.shuffle(deck)

    # each player needs 3 more cards to make a 5-card starting hand
    our_extra = [deck.pop() for _ in range(3)]
    opp_extra = [deck.pop() for _ in range(3)]
    hand0 = list(our_cards) + our_extra
    hand1 = list(opp_pair_cards) + opp_extra
    rng.shuffle(hand0); rng.shuffle(hand1)
    hand0.append(deck.pop())  # player 0 draws before their first decision

    empty_tables = [[],[],[],[]], [[],[],[],[]]
    state = S.State(hands=(tuple(hand0), tuple(hand1)), tables=(tuple(tuple(c) for c in empty_tables[0]), tuple(tuple(c) for c in empty_tables[1])),
                     burned=(False, False), deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)

    # force each player's first opportunity to commit their designated
    # cards to target_col; after both have committed, hand off to normal play
    committed = [False, False]
    my_cards_remaining = [list(our_cards), list(opp_pair_cards)]
    burn_cards = [None, None]
    while not S.is_terminal(state) and not (committed[0] and committed[1]):
        p = state.to_move
        if not committed[p] and my_cards_remaining[p]:
            card = my_cards_remaining[p].pop(0)
            action = ('play', card, target_col)
            if not my_cards_remaining[p]:
                committed[p] = True
        else:
            action = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if action[0] == 'burn':
            burn_cards[p] = action[1]
        state = S.step(state, action)

    # continue normally for the rest of the game
    while not S.is_terminal(state):
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0] == 'burn': burn_cards[p] = a[1]
        state = S.step(state, a)

    return state

def run_category(label, our_cards, opp_pair_cards, n, base_seed):
    wins = losses = ties = 0
    for i in range(n):
        state = build_forced_game(opp_pair_cards, our_cards, target_col=0, seed=base_seed+i)
        ra, rb = S.hand_rank(state.tables[0][0]), S.hand_rank(state.tables[1][0])
        if ra > rb: wins += 1
        elif rb > ra: losses += 1
        else: ties += 1
    print(f"{label:30s}: won {wins:5d}  lost {losses:5d}  tied {ties:3d}   (win rate {100*wins/n:.1f}%)")
    return wins, losses, ties

if __name__ == '__main__':
    N = 3000
    OPP_PAIR = [(9,0), (9,1)]   # fixed baseline: opponent opens with a pair of 9s
    print(f"Opponent baseline: pair of 9s. N={N} games per category.\n")

    categories = {
        "Higher pair (KK)":        [(13,0),(13,1)],
        "Same-rank pair (99, tiebreak only)": [(9,2),(9,3)],
        "Lower pair (44)":         [(4,0),(4,1)],
        "Suited low (3s,6s)":      [(3,0),(6,0)],
        "Suited high (Js,Ks)":     [(11,0),(13,0)],
        "Unrelated high cards (K,Q)": [(13,1),(12,2)],
        "Unrelated low cards (2,5)":  [(2,1),(5,2)],
        "Connected (7,8)":         [(7,0),(8,1)],
    }
    for label, cards in categories.items():
        run_category(label, cards, OPP_PAIR, N, base_seed=hash(label) % 100000)
