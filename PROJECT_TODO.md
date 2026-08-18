# Project: AI Bot for 2-Player Open-Tableau Poker

This document exists to bring a new reader (human or LLM) up to speed on
this project from scratch: what the game is, what's been built, what's
been validated through simulation, what's broken and fixed, and what's
left to do. Treat every "validated" claim below as backed by actual
simulation data gathered during development, not intuition — the whole
project has been built on a strict discipline of "test empirically before
trusting," because nearly every plausible-sounding idea in this game
turned out to need at least one round of real debugging before it
actually worked.

---

## 1. The Game

**2-Player Open-Tableau Poker (52-card exhaustion).**

- Standard 52-card deck, no jokers. 2 players, A and B.
- Each player has **4 open table columns** (up to 5 cards each, face up)
  and a **private 5-card hand** (hidden). There is also a one-time
  **burn**: each player may, exactly once per game, discard a card face
  down instead of playing it.
- **Setup:** deal 5 cards to each player. 42 cards remain as the draw
  deck.
- **Turn order:** alternating, Player A first. **Each turn, the active
  player DRAWS FIRST, then decides what to play/burn.** (This was a real
  rule correction mid-project — earlier code assumed play-then-draw. The
  practical consequence: at decision time, a player's hand has **6
  cards**, not 5, since they've already drawn for that turn.)
- A play places 1 card into one of the player's own 4 columns (capped at
  5 cards each). A burn discards 1 card face down (usable only once per
  game).
- The game ends when the 42-card deck is exhausted. **Proven invariant:**
  this always takes exactly 42 total turns (21 per player), and burning
  is therefore *mathematically forced* eventually — 20 plays (4 columns ×
  5 slots) + 1 burn = 21 turns per player, so every column always ends
  up exactly full (5 v 5), and both hands always end at exactly 5 cards.
- **Showdown:** 5 total hands are compared via standard poker ranking —
  the 4 columns (A's col N vs B's col N) plus the 2 hidden hands.
  **Whoever wins 3 of these 5 wins the game** (a majority-of-5 format).

---

## 2. Architecture / File Inventory

The project is on GitHub (`Sjviray814/Chinese-Poker-GTO`, `main` branch;
see §8.8). Top level holds the core deliverables; `research/` holds
reusable analysis tooling referenced by name throughout this document;
`research/scratch/` holds the full remaining one-off exploration/sweep
history for anyone wanting the complete experimental trail.

### Core engine
- **`solver.py`** — the authoritative Python engine. Contains: the
  hand-ranking evaluator (`hand_rank`), the game state machine (`State`,
  `step`, `legal_actions`, `is_terminal`), the heuristic policy
  (`heuristic_action` — the rollout policy inside search; `fit_score`
  is its scoring function), a SEPARATE `action_priority` /
  `fit_score_hand_aware` pair (tree exploration ordering only — see
  §8.6 for why these two are deliberately different functions with
  different scoring), the column win-probability estimator (§8), and
  the ISMCTS/PIMC search (`mcts_search`, `determinize`, `solve`). **This
  is the bot** — everything else either tests it, extends it, or ports
  it. Fully self-contained (no imports from `research/`).

### User-facing tools
- **`board_solver.html`** — single-page board-state builder: manually
  enter a hand/board via a felt-table UI, click "solve," get the
  engine's move recommendation. Self-contained (JS port of the Python
  engine embedded inline).
- **`play_vs_bot.html`** — full interactive live game against the bot in
  a browser. Same JS engine, wrapped in an actual turn-by-turn game loop
  with card selection, burn handling, an async "bot is thinking"
  indicator, and (as of §8.7) a post-game reveal of the bot's hidden
  hand alongside the full final board.

### research/ — reusable analysis tooling
- **`matchup_harness.py`**, **`multicolumn_harness.py`** — generalized
  harnesses for forcing specific board states (arbitrary column depth,
  arbitrary opponent archetypes) and measuring win rates via full
  self-play. These are the workhorses behind most of the scenario-coverage
  findings in §4.
- **`analytic_eval.py`** — one of three successive attempts at replacing
  the rollout mechanism with a cheaper evaluator (see §5 — all three
  ultimately lost to the real rollout; `microsim_eval.py`/`microsim_v3.py`
  are the other two, kept in `research/scratch/`).
- **`prob_fitscore.py`** — the completed, validated-to-parity
  probability-informed replacement for the flat-constant scoring inside
  `heuristic_action`. See §6.
- **`column_winprob.py`** — the hypergeometric column win-probability
  estimator from §8, validated to within ~7 points across every category
  tier and hand-type tested.
- **`fast_heuristic.py`** — the table-based categorize-then-lookup
  scoring system from §8.5, built as a fast alternative to live
  probability calculation.
- **`pivotal_estimator.py`** — the validated pivotality math (§4's
  "marginal value ≠ absolute value" finding, formalized) — not yet
  re-integrated post-§8.6 (see §9 TODO item 4).

---

## 3. Completed Foundational Work

- Corrected a fundamental rule misunderstanding (draw-then-play, not
  play-then-draw) that required rewriting the state machine, including a
  subtle terminal-detection fix (`done` flag distinct from "deck empty",
  since the very last mover still owes a decision after drawing the
  final card).
- Built and validated a full ISMCTS/PIMC search engine from scratch:
  determinization of hidden information, UCT tree search, heuristic
  rollout policy, progressive-bias expansion ordering.
- **Major efficiency work**, each validated with before/after
  throughput benchmarks:
  - Structural sharing (immutable state, avoid deep-copying the whole
    board every tree node) — ~4-5x speedup.
  - Removed `Counter`-based overhead from the hottest function
    (`partial_strength`) after profiling found it was 65% of runtime —
    additional ~3.5x speedup.
  - Symmetry reduction: when two of a player's own columns have
    identical content on *both* sides of the matchup, they're
    provably interchangeable — collapses branching factor early-game.
  - Net effect: roughly 4-6x more search throughput than the original
    implementation, confirmed via controlled A/B throughput tests.
- Built two real, tested UIs (`board_solver.html`, `play_vs_bot.html`),
  including finding and fixing several real bugs along the way (missing
  burn-card exclusion in determinization, an unsafe heuristic fallback
  with no legal actions, and — memorably — leftover Node.js-only debug
  code that silently broke every single bot decision in the browser
  because Node has a `global` object by default and browsers don't, so
  it never showed up in any server-side test).

---

## 4. Validated Strategic Findings (reference data)

These are backed by real simulation (sample sizes noted where it
matters), not guesses. Treat anything *not* on this list as unvalidated.

### Foundational heuristic principles (baked into `heuristic_action`)
- **Rank-stacking (pairs/trips/quads) dominates flush-chasing.** A
  pair-priority bot beat a flush-priority bot 58.4%.
- **Spread your first ~4 moves across all 4 columns** before
  concentrating — beat blind stacking 65.3%.
- **Attack the opponent's weakest column**, don't reinforce your own
  strength or contest theirs — an attack-weak bot beat alternatives
  64-70% of the time in early testing.
- **Smart-open refinement (validated, integrated):** if your starting
  hand already contains a known pair, play one card of that rank
  immediately during the opening spread instead of blindly playing your
  lowest card — 53.08% win rate at n=15,000. A more aggressive
  "force-stack both copies immediately" variant was tested and found
  *worse* (48.9% head-to-head) — the simpler version is correct.
- **Trips-hold refinement (validated, integrated):** if your starting
  hand contains trips (3+ of a rank), **hold** it — don't rush it out
  during the opening; deploy it once you can see where the opponent is
  actually weak. Immediate deployment won only 41.2% vs. holding's
  55.2% (14-point gap, same deals, ~23 standard errors apart). This does
  **not** extend to mere pairs, even Aces — confirmed the category
  boundary (pair = deploy now, trips = hold) is exactly right.

### Column-matchup findings (from extensive `matchup_harness.py` testing across depths 1-4)
- **Category hierarchy dominates rank almost everywhere** — trips beats
  two pair even at a much lower rank; two pair beats a single pair
  regardless of rank.
- **Quads are (almost) unbeatable.** A column with established quads can
  only be beaten if you hold trips of a *higher* rank than theirs
  (giving ~51% via completing higher quads yourself); trips of a *lower*
  rank gives exactly 0%, no matter how you play it.
- **Kickers matter more than expected.** A matching pair with no kicker
  info is a coin flip (48.9%); the same matchup with the opponent
  additionally holding a strong kicker collapses to 23.1%.
- **Straight draws are worse than flush draws, and both are bad.** A
  4-card straight draw (one card short) loses to a mere pair 99.6% of
  the time. A 4-card flush draw loses to a pair 91.8% of the time. Suits
  in general matter little (a kicker's suit relationship to an existing
  pair made no measurable difference).
- **Burn status has a real but modest effect** (~2-4 percentage points
  depending on who's already burned).
- **The same resource is worth wildly different amounts depending on
  where you place it.** A pair of 7s: 76% win rate against a weak
  opponent column, 39% against an equal-tier pair, 20% against
  established trips.

### Multi-column / resource-allocation findings
- **Split vs. concentrate depends on context, not a universal rule.**
  - Two separate starting pairs, target columns both *blank*: **split**
    them across different columns (52.6% vs. 45.5% concentrated) — a
    redundant second pair in the same column wastes a whole column's
    worth of potential.
  - Two separate starting pairs, target columns *already show opponent
    weakness*: **concentrate** instead (60.1% vs. 53.7% split) — the
    built-in "attack weak column" logic already covers an easy column on
    its own, so reinforcing an already-fine spot wastes the resource;
    better to make one column overwhelming.
  - Trips: **always concentrate**, never split into pair+single (59.4%
    vs. 43.2%) — breaking trips apart *downgrades your category tier*
    for almost no compensating value.
- **Marginal value ≠ absolute value.** Contesting an opponent's strong
  column with a decent resource is the worst option even though its
  absolute win probability isn't the lowest — because the *marginal*
  contribution of your resource there is tiny (a category ceiling caps
  what's achievable). A fresh, undifferentiated column often has a
  bigger marginal delta than either attacking weakness or contesting
  strength, because the built-in weak-column logic already handles easy
  spots on its own.
- **Pivotality (validated mathematically and empirically):** the true
  value of any column-level probability improvement is (marginal delta)
  × (how pivotal that column is right now). Derived closed-form:
  `∂P(overall win)/∂p_i = P(exactly 2 wins among the other 4 sub-hands)`.
  Empirically validated: the *identical* column-level improvement was
  worth +4.0 percentage points of overall win rate when 3 wins were
  already secured elsewhere, vs. +21.1 points when the other columns
  were genuinely split — a >5x difference for the same move, purely from
  context.

---

## 5. Things Tried and Abandoned (with reasons — don't redo these)

- **Three attempts to replace the rollout mechanism with a cheaper
  evaluator** (`analytic_eval.py` v1, `microsim_eval.py` v2,
  `microsim_v3.py` v3), each fixing a real diagnosed flaw in the
  previous one (independence assumption → cross-column competition →
  opponent-awareness), and each still losing to the real rollout in full
  MCTS play (margins -1.67, -1.67, -1.33 respectively). **Conclusion:**
  every one of these was a *batch/one-shot* allocation, while the real
  rollout is *sequential and reactive* — each simulated turn responds to
  what's actually happened so far. That structural difference, not
  scoring quality, appears to be the real gap. **Do not retry this
  direction without addressing sequentiality specifically.**
- **A first pivotality-weighted heuristic** (`pivotal_heuristic.py`) that
  replaced the *entire* scoring function at once — lost badly (39.6%),
  even after fixing one real bug (missing hidden-hand term). Root
  cause diagnosed as likely: (a) the underlying win-probability estimator
  it depended on was too crude, and (b) replacing a well-debugged working
  system wholesale re-exposes all the bugs that were already found and
  fixed in the old one. **Current plan (in progress, see §8): build and
  validate the win-probability estimator to a high standard FIRST,
  standalone, before touching pivotality integration again.**

---

## 6. The `prob_fitscore.py` Saga (completed — useful as a debugging case study)

Goal: replace the flat constant `rank_matches * 12` inside the existing,
validated `fit_score`/`heuristic_action` with real hypergeometric
completion odds, while keeping everything else (opponent-aware
`weak_bonus`, opening-spread rule) untouched. This took **five rounds of
real bugs**, each one a legitimate, specific, fixable modeling error —
worth reading as a template for how to debug this kind of thing:

1. Empty-column speculative credit (didn't matter much in practice —
   the opening rule already prevents this path from being hit often).
2. **Hand-matching false credit**: treating a matching card still
   sitting in hand as a "free" guaranteed future addition to a column
   made a non-matching filler card look nearly as good as immediately
   placing the real match. Fixed by not crediting this for
   move-comparison purposes.
3. Burn threshold miscalibrated for the new score scale (was tuned for
   the old flat-constant range) — recalibrated.
4. **Junk-card speculative inflation** (the big one): the hypergeometric
   formula for "will more of this rank arrive" doesn't care what card is
   being placed *right now* — so a totally unrelated filler card was
   getting nearly as much credit as the real match, collapsing the gap
   between good and bad choices from ~22x down to ~2.5x, letting
   `weak_bonus` override real synergy far too often. Fixed by only
   applying the probability computation when the candidate card actually
   matches something already in the column.
5. **Tie-break misclassification**: comparing a candidate's rank against
   a single arbitrarily-chosen "most common rank" (via Python's
   `Counter.most_common` tie-breaking) instead of checking whether it
   matches *any* rank already present — this silently misclassified real
   pairing opportunities as "no match" whenever a column had several
   different ranks tied at count 1 (extremely common pre-pair).

**Final result:** exactly 50.0% at large sample size (n=4000-8000) —
genuine parity with the original flat-constant heuristic, validated with
both win/loss and finer-grained continuous metrics (total category
value, sub-hands won) to make sure a real accumulating edge wasn't being
missed by a coarse signal. **This is not yet a win, but it's no longer a
loss**, and it's a defensible, real-probability-based foundation to build
on rather than a hand-tuned constant.

---

## 7. Methodology Notes (apply these going forward)

- **Every "this should obviously work" idea in this project has needed
  real debugging.** Don't trust a theoretically-motivated change until
  it's been validated via actual simulation, ideally at a large enough
  sample size to rule out noise (repeatedly, apparent 51-53% edges at
  n=2000-3000 turned out to be pure noise at n=8000+).
- **Cheap validation before expensive integration.** Test new scoring
  logic via fast heuristic-vs-heuristic self-play (no search) before
  wiring it into the full, slow MCTS pipeline — this pattern caught
  every real bug in this project days before it would have been found
  in an expensive full-search benchmark.
- **When a result looks surprising, check for a measurement bug before
  believing it.** Multiple "big findings" in this project turned out to
  be artifacts (a self-serving-bias confound in an early win-probability
  trace experiment, a mis-copied ground-truth value, a Node.js-only
  global accidentally left in shipped code) — always sanity-check with a
  smaller, targeted debug print before trusting a dramatic number.
- **Fix bugs at the root cause, not with special-case patches.** Several
  of the `column_winprob.py` bugs (see §8) were literally the same
  category of error (using the wrong sample size for a hypergeometric
  calculation) recurring in different functions — once recognized, the
  fix generalized cleanly instead of needing three separate patches.

---

## 8. RESOLVED: `column_winprob.py` win-probability estimator (see below for full arc)

**Status: the estimator itself is now well-calibrated and DONE.** Every
validation scenario tested landed within ~7 percentage points of real
simulated ground truth (down from an initial worst case of +22 points).
The two structural bugs that mattered most: (1) using the wrong sample
size for hypergeometric draws in multiple places (a column can only ever
receive its own remaining slots, not the player's whole future-draw
budget) and (2) the model being unable to represent two pair / full
house at all until it was extended to track the top 2 candidate ranks
jointly via a proper multivariate hypergeometric distribution (verified:
a plain unpaired 2-card hand actually reaches at least a pair 97.5% of
the time in real play, with two pair + full house alone accounting for
41% of outcomes -- a single-tracked-rank model structurally cannot
express this).

**Integration attempt and an important correction:**
- Consolidated the validated estimator directly into `solver.py` (not
  imported, to avoid a circular dependency with `column_winprob.py`,
  which itself imports `hand_rank` from `solver.py`).
- As a STANDALONE policy (`heuristic_action_winprob`), it beats the
  original heuristic (`fit_score` + crude `weak_bonus`) ~53.2% head to
  head, validated across 5,500 games in three independent batches, all
  individually above 50% -- a real, reproducible edge (~4.7 standard
  errors).
- **However, a direct MCTS-level A/B test (not just raw-heuristic
  self-play) showed it LOSES badly as a rollout policy (2-6 in a small
  n=8 search-level test).** Root cause, confirmed by direct measurement:
  it's ~43x slower per call (43.1 rollouts/sec vs 1862.3/sec), not the
  ~4-8x initially estimated from games/sec numbers. Under MCTS's fixed
  time budget, this means ~43x fewer completed rollouts, and the search
  becomes far noisier from having so much less signal to average over --
  this costs far more in search quality than the per-rollout accuracy
  gain returns.
- **Correction applied:** `heuristic_action` (the name `rollout()` calls
  thousands of times per search) was kept as the FAST original version.
  The win-probability-based logic lives separately as
  `heuristic_action_winprob` -- validated as a genuinely better
  STANDALONE policy, not yet proven useful inside the search itself.

**This is an important, generalizable lesson for the project, not just a
one-off setback:** a policy that's better in isolation is not
automatically better as a component INSIDE a system with a fixed
computational budget, if it's significantly more expensive to evaluate.
Any future policy upgrade destined for rollout or `action_priority` needs
its own MCTS-level (not just raw self-play) validation before being
treated as an improvement, and its per-call cost needs to be checked
early, not assumed from a different benchmark's numbers.

---

## 8.5. The `fast_heuristic.py` Saga and Two Real, User-Reported Bugs

After §8's win-probability estimator was validated, it was wired into
MCTS as a candidate rollout policy and found to be a clear net loss at
the search level despite a strong raw-heuristic edge (~43x slower per
call meant far fewer completed rollouts — the same "speed beats
per-rollout accuracy" lesson as the earlier analytic-evaluator attempts
in §5). Rather than abandon the idea, the response was to rebuild it as
a **fast, table-based categorize-then-lookup system** instead of live
probability calculation — `fast_heuristic.py`. Key points from that
effort, since the file inventory should mention it:

- `categorize_column()` + a hand-tuned `ARCHETYPE_TIER` table replaced
  exact hypergeometric computation with O(1)-ish lookups, calibrated
  against the same validated matchup data from §4.
- Two real implementation bugs were found and fixed via profiling (not
  guessing): `collections.Counter` + `.most_common()` was serious
  overkill for 5-card-max columns (the same class of mistake already
  fixed once in `partial_strength` early in the project) and redundant
  per-candidate recomputation of the *unchanging* opponent side. Fixing
  both brought the speed penalty from 43x down to ~3.2x.
- Getting the actual *scoring* right took real iteration too: an early
  version scored a near-certain trips-vs-trips win LOWER than a
  coin-flip empty-column play, because raw tier-difference wasn't
  expressed on a consistent "how decisive is this" scale across
  different category tiers — fixed by calibrating the within-tier rank
  bonus per tier against real validated anchors (pair vs. trips) instead
  of one flat rate.
- This work is preserved in the repo's `research/` folder as a real,
  useful design pattern (rule-table lookup beats live probability
  calculation for a rollout-speed-constrained context) even though, as
  below, the two bugs that actually shipped to the live bot were found a
  different way.

## 8.6. Two Real Bugs Found From Actual Observed Play (both fixed and live)

This is the most important recent development: **the user reported the
bot's real, in-browser play looked aimless, and two rounds of screenshot
evidence led to two distinct, confirmed, fixed bugs** — not vibes, actual
root causes traced to specific lines of scoring code.

**Bug 1 — `straight_w` rewarded the single worst validated strategy in
the game.** `fit_score`'s `straight_w` term gave a smooth, monotonically
decreasing bonus for placing a card numerically close (but not matching)
an existing card — e.g. a 6 next to an existing 5 — worth up to 2.0
points, often the single largest component of the score once no real
rank match existed anywhere. But §4 already established, extensively,
that pursuing straights is the worst strategy in this game (loses
84-99.6% of the time to a simple response). The scoring function was
directly rewarding what the strategy research had already proven was
wrong. Fixed by setting `straight_w=0.0`.

**Bug 2 — no mechanism at all discouraged piling unrelated cards into an
already-cluttered column.** Confirmed directly: a column already holding
one unrelated "junk" card scored *exactly* the same as a completely
empty column for a new non-matching candidate. There was no cost to
concentrating unrelated cards together instead of spreading them across
emptier columns, which is how a column ends up looking like it was
"given up on" — three or four cards with no shared rank, no plan. Fixed
with a `junk_penalty_w` term: placing a non-matching card into a column
that already holds unrelated cards (and has no pair of its own yet) is
now penalized proportional to how many such cards have already piled up.

**The critical methodological lesson from deploying these**: the first
attempt fixed only `action_priority` (which orders which branches the
search tree explores first) and got an *inconclusive* MCTS-level result
(44%, then 5-5 on a related sub-test) — because `action_priority` never
touches the actual win-rate *estimates* that determine the bot's real
move; those come entirely from rollout simulations, i.e. `heuristic_action`
/ `fit_score`, which were still unfixed. **A user screenshot taken after
the `action_priority`-only fix confirmed the bad behavior was completely
unchanged in real play** — direct, concrete evidence that fixing
exploration order without fixing the underlying value estimates doesn't
change what the bot actually does. Moving both fixes into `fit_score`
itself (the rollout policy) resolved it, validated at the MCTS level as
strong, clean wins (8-2 for straight-removal alone; 8-2 again for the
junk-penalty fix in rollout). **General lesson, worth remembering for
any future scoring change: identify which of {`action_priority`
(exploration order) vs. `heuristic_action`/`fit_score` (rollout, actual
value estimates)} the change needs to live in, and validate at the MCTS
level in that exact role — a fix validated in the wrong layer can look
totally inert in real play despite being clearly correct in isolation.**

Also discovered along the way: naively combining the earlier
hand-awareness fix (crediting a candidate for matching another card
still in hand — itself validated as safe *only* in `action_priority`,
regressing badly in rollout) with the straight-removal fix, both in
`action_priority`, produced a **clear MCTS-level loss (2-8)** even
though each fix independently tested fine or well (hand-awareness alone:
neutral 44%; straight-removal alone: 8-2 win). Resolved by reducing the
hand-synergy weight (7 → 2). **General lesson: two independently-safe
changes can interact badly — always test the actual combination being
shipped, not just each piece in isolation.**

### Current live scoring split (as of this writing)

- **`fit_score`** (used by `heuristic_action`, the rollout policy — the
  function whose value estimates actually determine the bot's real
  move): `straight_w=0.0`, `junk_penalty_w=1.5`. No hand-awareness here
  — validated to regress at the MCTS level.
- **`fit_score_hand_aware`** (used only by `action_priority`, which just
  orders tree exploration — every action still gets tried eventually
  regardless): `straight_w=0.0`, `hand_synergy_w=2.0` (reduced from an
  initially-tried 7 after the bad-interaction finding above),
  `junk_penalty_w=1.5`.
- Both fixes are ported identically into the JS engine inside
  `play_vs_bot.html` and `board_solver.html`, cross-verified against the
  Python reference on the exact scenarios that motivated each fix, plus
  a 100-game full-invariant regression suite (52 cards accounted for, 42
  turns, every column reaching exactly 5, both hands at exactly 5 at
  game end) run after every change.

## 8.7. `play_vs_bot.html`: post-game reveal

The end-of-game screen used to replace the entire board with just a
win/loss summary, so there was no way to review what actually happened.
Fixed: the full board (both sides, all 4 columns) now stays visible
alongside the summary, and the bot's hidden hand — never shown during
play — is revealed once the game ends. Verified the reveal panel stays
hidden throughout play and correctly populates with the bot's real
5-card hand immediately after `finishGame()`, via a full simulated game
run through the actual DOM-interacting code path (not just a logic
check).

## 8.8. Repository

The project is now on GitHub: `Sjviray814/Chinese-Poker-GTO` (`main`
branch). Structure: `solver.py`, both `.html` tools, `README.md`, and
this file at the top level; `research/` holds the reusable analysis
modules referenced by name throughout this document
(`column_winprob.py`, `matchup_harness.py`, `multicolumn_harness.py`,
`fast_heuristic.py`, `prob_fitscore.py`, `analytic_eval.py`,
`pivotal_estimator.py`); `research/scratch/` holds the full remaining
one-off exploration/sweep/debug script history (~58 files) for anyone
wanting the complete experimental trail rather than just the curated
tooling. A repo-scoped Personal Access Token is configured on the local
remote for continued pushes (user-provided, expires roughly a month from
setup — worth rotating or revoking after that, or once this phase of
work wraps up).

---

## 9. TODO — Near Term

1. **Get real player feedback on the two shipped bug fixes.** Both the
   straight_w removal and the junk-penalty fix are validated at the MCTS
   level (8-2 each), but the *original* motivation for both was specific
   user screenshots of real play looking aimless — the real confirmation
   is whether play now visibly looks better in practice, not just the
   aggregate number. Worth actively watching for a few more sessions.
2. **The opening-phase spread/pair/trips-hold rule is a hard-coded rule
   inside `heuristic_action`, applied only during rollout simulation —
   it is NOT hard-enforced at the real, root-level decision.** `solve()`
   is pure tree search from scratch with no special-casing for "we're
   still in the opening." This was investigated (mid-conversation) as a
   possible explanation for unreliable early-game play, but budget
   constraints meant it wasn't conclusively resolved — worth either (a)
   directly special-casing the opening rule at the root (skip search
   entirely for the deterministically-known-correct first few moves,
   which would also be strictly faster), or (b) more targeted MCTS-level
   testing specifically of early-game decision reliability across a
   range of budgets to see how much this actually matters in practice.
3. **Extend the "found via real observed play" debugging pattern
   deliberately**, rather than waiting for it to happen incidentally.
   Both shipped bugs this round were found by tracing exact
   user-reported bad moves back to specific lines of scoring code, which
   caught things pure aggregate win-rate testing had NOT caught (the
   straight_w bug had shipped, un-flagged, for the entire session up to
   that point despite extensive self-play validation of everything
   around it). Consider periodically constructing "does this look like
   good play to a human" spot-checks, not just win-rate benchmarks.
4. **Re-integrate pivotality** (`pivotal_estimator.py`'s math is already
   validated) now that both the win-probability estimator (§8) and the
   rollout/action_priority scoring (§8.6) are in a solid, validated
   state — apply the same "identify the right layer, validate at the
   MCTS level in that exact role" discipline from §8.6 rather than
   assuming either integration surface is safe by default.
5. **`heuristic_action_winprob`** (§8's exact win-probability estimator)
   remains validated as a strong *standalone* policy (~53%) but was never
   made fast enough for rollout (~24-43x) nor conclusively proven at the
   root/action_priority level either. Given `fast_heuristic.py` (§8.5)
   achieved a similar goal (real-play-informed scoring) at much better
   speed via a different mechanism (table lookup vs. live probability),
   it's an open question whether `heuristic_action_winprob` is still
   worth pursuing further or has been superseded in practice — worth an
   explicit decision rather than leaving both half-finished in parallel.

## 10. TODO — Medium Term

- Re-run the full MCTS-vs-MCTS and MCTS-vs-heuristic benchmarks with the
  CURRENT, fully-updated scoring (post §8.6) to get a clean, up-to-date
  baseline before building further on top of it — the last full
  MCTS-level benchmarks predate both of this round's fixes.
- Extend column-matchup scenario coverage into remaining gaps: full
  house/quads already in a 6-card starting hand (never tested, rare but
  real), the hidden hand's specific dynamics (everything so far is
  open-column matchups; the hidden hand's composition *churns* rather
  than filling monotonically, and no testing has been done on it
  directly), and genuine multi-column simultaneous tradeoffs beyond the
  handful already tested.
- Build a **proper statistical benchmark harness** with confidence
  intervals, not just win/loss records at ad hoc sample sizes -- flagged
  repeatedly as a real gap, and now doubly relevant given several
  MCTS-level decisions this round were made from n=8-10 samples (the
  best affordable given ~150-180s per batch) -- these were treated as
  suggestive-but-not-final evidence throughout, consistent with that
  small a sample, but a cheaper way to get more confident MCTS-level
  reads would materially speed up future iteration.
- **In-game logging**: record the solver's actual top-3 recommendations
  and confidence at each real turn during live play, so future
  disagreements about "did the bot play well" can be diagnosed from real
  data instead of a reconstructed-after-the-fact board -- this would
  have made the §8.6 bug hunt significantly faster (both bugs were
  found by manually reconstructing approximate board states from
  screenshots rather than exact logged decisions).
- Now that the repo is on GitHub (§8.8), consider basic CI (even just
  "run the 100-game invariant suite on push") to catch regressions
  automatically rather than relying on remembering to re-run it by hand
  after every change, which has been the pattern so far.

## 11. TODO — Long Term / Further Out

- **Parallelism across determinizations.** Every determinization in the
  PIMC loop is fully independent — this is close to embarrassingly
  parallel and currently runs single-threaded. Identified early as
  probably the single biggest unclaimed performance lever, never
  implemented.
- **A true shared-tree ISMCTS**, as opposed to the current
  independent-tree-per-determinization (PIMC) approach — accumulates
  statistics across determinizations into one persistent tree rather
  than discarding and rebuilding for each one. Well-documented in the
  literature as more sample-efficient; not yet attempted here.
- **Real opponent modeling.** Determinization currently samples the
  opponent's hidden hand uniformly at random. If playing the same
  opponent repeatedly, biasing that sampling toward their actual
  observed tendencies (rank-stacking vs. flush-chasing, aggressive vs.
  passive column commitment) is a real potential strength jump — bigger
  scope than anything attempted so far (needs move-history tracking
  plumbed through the whole system).
- **Revisit whether the tree should be wide/deep with a crude leaf value
  (current shape) or narrow/shallow with a strong equity model** — an
  open structural question raised mid-project (this game resembles
  poker's "get the equity estimate right" more than chess's "search many
  forcing lines" character) that was explicitly deferred until the
  equity model itself was proven strong. Worth revisiting once §9-10 are
  further along.
- **A genuine opening book**, generated by very deep offline search on
  canonicalized starting-hand types (suit-identity and slot-choice are
  both provably irrelevant, collapsing the true opening decision space
  a great deal) — partially superseded by the validated smart-open/
  trips-hold *rules*, which handle much of what a book would need, but
  the no-synergy card-ordering question and near-miss/suited-connector
  prioritization remain open and were flagged as good candidates for
  either a rule or a small book.


- **Parallelism across determinizations.** Every determinization in the
  PIMC loop is fully independent — this is close to embarrassingly
  parallel and currently runs single-threaded. Identified early as
  probably the single biggest unclaimed performance lever, never
  implemented.
- **A true shared-tree ISMCTS**, as opposed to the current
  independent-tree-per-determinization (PIMC) approach — accumulates
  statistics across determinizations into one persistent tree rather
  than discarding and rebuilding for each one. Well-documented in the
  literature as more sample-efficient; not yet attempted here.
- **Real opponent modeling.** Determinization currently samples the
  opponent's hidden hand uniformly at random. If playing the same
  opponent repeatedly, biasing that sampling toward their actual
  observed tendencies (rank-stacking vs. flush-chasing, aggressive vs.
  passive column commitment) is a real potential strength jump — bigger
  scope than anything attempted so far (needs move-history tracking
  plumbed through the whole system).
- **Revisit whether the tree should be wide/deep with a crude leaf value
  (current shape) or narrow/shallow with a strong equity model** — an
  open structural question raised mid-project (this game resembles
  poker's "get the equity estimate right" more than chess's "search many
  forcing lines" character) that was explicitly deferred until the
  equity model itself was proven strong. Worth revisiting once §9-10 are
  further along.
- **A genuine opening book**, generated by very deep offline search on
  canonicalized starting-hand types (suit-identity and slot-choice are
  both provably irrelevant, collapsing the true opening decision space
  a great deal) — partially superseded by the validated smart-open/
  trips-hold *rules*, which handle much of what a book would need, but
  the no-synergy card-ordering question and near-miss/suited-connector
  prioritization remain open and were flagged as good candidates for
  either a rule or a small book.
