"""
Full-bot-vs-full-bot testing framework.

This is the new standard for validating any proposed change, per direct
instruction: do NOT test isolated heuristic functions against each other
in a vacuum. Instead, snapshot the CURRENT complete, deployed bot
(everything integrated -- opening hard-rule, statistical-tie fallback,
action_priority, rollout policy, all of it) as a baseline module, apply
the proposed change to a separate copy, and play the two COMPLETE bots
against each other using their own real solve()/MCTS pipelines end to
end. This is what actually would have caught the hand_synergy_w=7 +
straight_w=0 bad interaction earlier, and it's the only test that
reflects what a real player actually experiences.

Usage: save a baseline snapshot to research/snapshots/ BEFORE making a
change, apply the change to the live solver.py, then use this harness
to play baseline vs modified.
"""
import sys
import random
import importlib.util


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def play_full_bot_game(mod0, mod1, seed, time_budget=0.4, iters_per_det=60):
    """Plays ONE complete game using each side's own full solve()/MCTS
    pipeline (not just heuristic_action in isolation) for every decision."""
    rng = random.Random(seed)
    deck = mod0.make_deck(); rng.shuffle(deck)
    hand0 = [deck.pop() for _ in range(5)]
    hand1 = [deck.pop() for _ in range(5)]
    hand0.append(deck.pop())
    tables = ((tuple(), tuple(), tuple(), tuple()), (tuple(), tuple(), tuple(), tuple()))
    state = mod0.State(hands=(tuple(hand0), tuple(hand1)), tables=tables, burned=(False, False),
                        deck_cards=tuple(deck), deck_pos=0, to_move=0, done=False)
    mods = [mod0, mod1]
    burn_cards = [None, None]
    while not mod0.is_terminal(state):
        p = state.to_move
        m = mods[p]
        ranked, dets, elapsed = m.solve(list(state.hands[p]), [list(c) for c in state.tables[p]],
                                          [list(c) for c in state.tables[1 - p]], state.burned[p],
                                          burn_cards[p], state.burned[1 - p],
                                          time_budget=time_budget, iters_per_determinization=iters_per_det,
                                          seed=rng.randint(0, 10**9))
        a = ranked[0][0]
        if a[0] == 'burn':
            burn_cards[p] = a[1]
        state = mod0.step(state, a)
    wins = [0, 0]
    for i in range(4):
        ra, rb = mod0.hand_rank(state.tables[0][i]), mod0.hand_rank(state.tables[1][i])
        if ra > rb: wins[0] += 1
        elif rb > ra: wins[1] += 1
    ra, rb = mod0.hand_rank(state.hands[0]), mod0.hand_rank(state.hands[1])
    if ra > rb: wins[0] += 1
    elif rb > ra: wins[1] += 1
    return wins, state


def run_matchup(baseline_path, modified_path, n, base_seed=0, time_budget=0.4, verbose=True):
    baseline = load_module(baseline_path, "baseline_bot")
    modified = load_module(modified_path, "modified_bot")
    mod_wins = base_wins = ties = 0
    import time as _time
    t0 = _time.time()
    for i in range(n):
        seed = base_seed + i
        if i % 2 == 0:
            wins, _ = play_full_bot_game(modified, baseline, seed, time_budget)
            mw, bw = wins[0], wins[1]
        else:
            wins, _ = play_full_bot_game(baseline, modified, seed, time_budget)
            mw, bw = wins[1], wins[0]
        if mw > bw: mod_wins += 1
        elif bw > mw: base_wins += 1
        else: ties += 1
        if verbose:
            print(f"  game {i+1}/{n}: MODIFIED {mod_wins} - BASELINE {base_wins} - ties {ties}  ({_time.time()-t0:.0f}s)")
    print(f"\nFULL-BOT RESULT: modified {mod_wins} - baseline {base_wins} - ties {ties}  over {n} games")
    return mod_wins, base_wins, ties
