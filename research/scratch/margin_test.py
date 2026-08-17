import random
import solver as S
from prob_fitscore import heuristic_action_v2

def play_game_full(strat0, strat1, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    burn_cards=[None,None]
    strategies=[strat0,strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](state.hands[p], state.tables[p], state.tables[1-p], state.burned[p], burn_cards[p])
        if a[0]=='burn': burn_cards[p]=a[1]
        state = S.step(state, a)
    cats0 = [S.hand_rank(c)[0] for c in state.tables[0]] + [S.hand_rank(state.hands[0])[0]]
    cats1 = [S.hand_rank(c)[0] for c in state.tables[1]] + [S.hand_rank(state.hands[1])[0]]
    wins0 = sum(1 for i in range(4) if S.hand_rank(state.tables[0][i]) > S.hand_rank(state.tables[1][i]))
    wins0 += 1 if S.hand_rank(state.hands[0]) > S.hand_rank(state.hands[1]) else 0
    wins1 = sum(1 for i in range(4) if S.hand_rank(state.tables[1][i]) > S.hand_rank(state.tables[0][i]))
    wins1 += 1 if S.hand_rank(state.hands[1]) > S.hand_rank(state.hands[0]) else 0
    return sum(cats0), sum(cats1), wins0, wins1

def old_strat(hand, own_table, opp_table, burned, own_burn_card):
    return S.heuristic_action(hand, own_table, opp_table, burned)
def new_strat(hand, own_table, opp_table, burned, own_burn_card):
    return heuristic_action_v2(hand, own_table, opp_table, burned, own_burn_card)

N = 3000
new_total_value = 0
old_total_value = 0
new_col_wins = 0
old_col_wins = 0
new_wins = old_wins = ties = 0
for i in range(N):
    seed = i
    if i % 2 == 0:
        nv, ov, nw, ow = play_game_full(new_strat, old_strat, seed)
    else:
        ov, nv, ow, nw = play_game_full(old_strat, new_strat, seed)
    new_total_value += nv
    old_total_value += ov
    new_col_wins += nw
    old_col_wins += ow
    if nw > ow: new_wins += 1
    elif ow > nw: old_wins += 1
    else: ties += 1

print(f"Games: {N}")
print(f"Win/loss record: new={new_wins} old={old_wins} ties={ties}  ({100*new_wins/N:.1f}% for new)")
print(f"Average total hand-category value per game: new={new_total_value/N:.3f}  old={old_total_value/N:.3f}")
print(f"Average sub-hands won per game (out of 5): new={new_col_wins/N:.3f}  old={old_col_wins/N:.3f}")
