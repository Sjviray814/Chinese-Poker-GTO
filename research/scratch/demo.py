import random, time
import solver as S

# --- Build a realistic mid-game board by simulating a partial game with
#     the heuristic policy on both sides (draw-then-play turn order),
#     then hand control to "root" for the next decision. ---
def simulate_partial_game(n_turns, seed=1):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())  # player 0 draws before their very first decision
    empty_tables = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0), tuple(hand1)), tables=empty_tables,
                     burned=(False,False), deck_cards=tuple(deck), deck_pos=0,
                     to_move=0, done=False)
    burn_cards = [None, None]
    for _ in range(n_turns):
        if S.is_terminal(state):
            break
        p = state.to_move
        a = S.heuristic_action(state.hands[p], state.tables[p], state.tables[1-p], state.burned[p])
        if a[0] == 'burn':
            burn_cards[p] = a[1]
        state = S.step(state, a)
    return state, burn_cards

state, burn_cards = simulate_partial_game(24, seed=7)
root = state.to_move          # whoever's turn it is now is "root" for the solver
opp = 1 - root

print(f"Deck remaining: {len(state.deck_cards) - state.deck_pos} cards | to move: player {root}")
print()
def show_table(table, label):
    print(label)
    for i,col in enumerate(table):
        cs = ' '.join(S.card_str(c) for c in col)
        print(f"  Col{i+1} ({len(col)}): {cs}")

show_table(state.tables[root], f"ROOT (player {root}) table:")
show_table(state.tables[opp], f"OPPONENT (player {opp}) table (visible):")
print(f"ROOT hand ({len(state.hands[root])} cards -- already includes this turn's draw): "
      f"{' '.join(S.card_str(c) for c in state.hands[root])}")
print(f"ROOT burned: {state.burned[root]}  OPPONENT burned: {state.burned[opp]}")
print()

t0=time.time()
ranked, dets, elapsed = S.solve(
    root_hand=state.hands[root],
    root_table=state.tables[root],
    opp_table=state.tables[opp],
    root_burned=state.burned[root],
    root_burn_card=burn_cards[root],
    opp_burned=state.burned[opp],
    time_budget=15.0,
    iters_per_determinization=150,
    seed=42,
    verbose=True,
)
print(f"\nSearched {dets} determinizations in {elapsed:.1f}s ({dets*150} total MCTS iterations)\n")
print("Ranked candidate moves (win-rate estimate, total visits):")
for a, wr, v in ranked[:8]:
    print(f"  {S.format_action(a):32s}  win-rate~{wr:.3f}   (n={v})")

print()
heuristic_pick = S.heuristic_action(state.hands[root], state.tables[root], state.tables[opp], state.burned[root])
print("Heuristic-only (no search) would have played:", S.format_action(heuristic_pick))
print("MCTS/PIMC solver recommends:               ", S.format_action(ranked[0][0]))
