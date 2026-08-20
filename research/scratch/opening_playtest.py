"""
Play the REAL, currently-deployed bot (full solve()/MCTS pipeline,
including both recent fixes) through the first 8 turns of many games,
using solve() for BOTH sides (a realistic bot-vs-bot opening), and print
a full move-by-move transcript for manual review.
"""
import random
import solver as S

def play_opening(seed, n_turns=8, time_budget=0.6):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0),tuple(hand1)), tables=tables, burned=(False,False),
                     deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    burn_cards = [None, None]
    moves = []
    for turn in range(n_turns):
        if S.is_terminal(state):
            break
        p = state.to_move
        ranked, dets, elapsed = S.solve(list(state.hands[p]), [list(c) for c in state.tables[p]],
                                          [list(c) for c in state.tables[1-p]], state.burned[p],
                                          burn_cards[p], state.burned[1-p],
                                          time_budget=time_budget, iters_per_determinization=60,
                                          seed=rng.randint(0, 10**9))
        a = ranked[0][0]
        moves.append((turn+1, p, a, ranked[0][1], ranked[0][2], dets))
        if a[0] == 'burn':
            burn_cards[p] = a[1]
        state = S.step(state, a)
    return moves, state

def print_transcript(seed, moves, final_state):
    print(f"=== Seed {seed} ===")
    for turn, p, a, wr, v, dets in moves:
        who = 'P0' if p == 0 else 'P1'
        print(f"  T{turn} ({who}): {S.format_action(a):28s} winrate={wr:.3f} visits={v} dets={dets}")
    for p in [0,1]:
        cols = [ [S.card_str(c) for c in col] for col in final_state.tables[p] ]
        print(f"  P{p} board: " + " | ".join("[" + ",".join(c) + "]" for c in cols))
    print()

if __name__ == '__main__':
    for seed in range(20):
        moves, final_state = play_opening(seed)
        print_transcript(seed, moves, final_state)
