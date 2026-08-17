import random, collections
import solver as S

def random_strategy(state, player, burn_cards):
    return random.choice(S.legal_actions(state))

def heuristic_strategy(state, player, burn_cards):
    return S.heuristic_action(state.hands[player], state.tables[player], state.tables[1-player], state.burned[player])

def play_game(strat0, strat1, seed):
    rng = random.Random(seed)
    deck = S.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    empty = ((tuple(),tuple(),tuple(),tuple()), (tuple(),tuple(),tuple(),tuple()))
    state = S.State(hands=(tuple(hand0), tuple(hand1)), tables=empty,
                     burned=(False,False), deck_cards=tuple(deck), deck_pos=0,
                     to_move=0, done=False)
    burn_cards = [None, None]
    strategies = [strat0, strat1]
    while not S.is_terminal(state):
        p = state.to_move
        a = strategies[p](state, p, burn_cards)
        if a[0] == 'burn': burn_cards[p] = a[1]
        state = S.step(state, a)
    wins = [0, 0]
    for i in range(4):
        ra, rb = S.hand_rank(state.tables[0][i]), S.hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1
    ra, rb = S.hand_rank(state.hands[0]), S.hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1
    elif rb > ra: wins[1] += 1
    return wins

def run_matchup(name, stratA, stratB, n, base_seed=0):
    a_wins = b_wins = ties = 0
    margins = collections.Counter()   # winner's margin, e.g. "3-2", "5-0"
    for i in range(n):
        seed = base_seed + i
        if i % 2 == 0:
            wins = play_game(stratA, stratB, seed)
            wa, wb = wins[0], wins[1]
        else:
            wins = play_game(stratB, stratA, seed)
            wa, wb = wins[1], wins[0]
        if wa > wb:
            a_wins += 1; margins[f"{wa}-{wb}"] += 1
        elif wb > wa:
            b_wins += 1; margins[f"{wb}-{wa}"] += 1
        else:
            ties += 1
    print(f"=== {name} ===  (n={n})")
    print(f"  A wins: {a_wins} ({100*a_wins/n:.1f}%)   B wins: {b_wins} ({100*b_wins/n:.1f}%)   ties: {ties}")
    total_decided = a_wins + b_wins
    for m in ["5-0","4-1","3-2"]:
        c = margins[m]
        print(f"  {m}: {c:4d}  ({100*c/total_decided:.1f}% of decided games)")
    print()
    return a_wins, b_wins, ties, margins

random.seed(1)
print("############################################")
print("# Baseline: identical (random) strategy on both sides")
print("# -- pure luck floor: skill is IDENTICAL (none), so any margin")
print("#    pattern here is 100% attributable to the deal + move order.")
print("############################################")
run_matchup("Random vs Random", random_strategy, random_strategy, 1500)

print("############################################")
print("# Skill gap: heuristic vs random")
print("# -- how often does raw luck let the weak side still win?")
print("############################################")
run_matchup("Heuristic vs Random", heuristic_strategy, random_strategy, 1500)

print("############################################")
print("# Skill controlled: identical (heuristic) strategy on both sides")
print("# -- pure luck floor again, but at the higher skill level: how much")
print("#    does outcome still swing on the deal even when both players")
print("#    play equally well?")
print("############################################")
run_matchup("Heuristic vs Heuristic", heuristic_strategy, heuristic_strategy, 1500)
