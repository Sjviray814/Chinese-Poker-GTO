# 2-Player Open-Tableau Poker — AI Bot

An ISMCTS/PIMC search engine and heuristic policy for a custom 2-player,
52-card exhaustion poker variant, plus two browser-based tools for using
and playing against it.

See **[PROJECT_TODO.md](PROJECT_TODO.md)** for the full project writeup:
game rules, architecture, everything validated this session (with real
numbers), things tried and abandoned (with reasons), and a prioritized
roadmap. That document is the best starting point for understanding this
project in depth — this README just covers what's in the repo and how to
run it.

## Contents

- **`solver.py`** — the core engine: hand evaluation, game state machine,
  the heuristic policy, and the ISMCTS/PIMC search. This is the
  authoritative implementation; everything else builds on it.
- **`board_solver.html`** — enter any board/hand state manually and get
  the engine's move recommendation. Self-contained (JS port of the
  engine embedded inline), runs entirely in the browser.
- **`play_vs_bot.html`** — play a full interactive game against the bot
  in the browser, including a post-game reveal of the bot's hidden hand.
- **`research/`** — reusable analysis tooling from the validation work
  behind this project (column win-probability estimation, matchup
  scenario harnesses, the probability-informed scoring experiments,
  etc.), referenced by name throughout PROJECT_TODO.md. Not wired into
  the live bot — kept for anyone continuing the research documented
  there.

## Running it

Both `.html` files are fully self-contained — just open them in a
browser, no build step or server needed.

For the Python engine:

```bash
python3 solver.py       # demo / sanity check, if __main__ block is present
```

Or import and use directly:

```python
import solver as S

ranked, dets, elapsed = S.solve(
    hand, own_table, opp_table,
    own_burned=False, own_burn_card=None, opp_burned=False,
    time_budget=8.0, iters_per_determinization=100,
)
```

## Status

Under active development — see PROJECT_TODO.md's TODO sections for
what's next. The bot has been iteratively refined against real observed
play (not just aggregate win-rate benchmarks), with each change validated
at the actual MCTS search level before being deployed, since this
project found repeatedly that raw self-play performance doesn't always
predict search-level performance.
