# ARC-AGI-3 Agent — learning game rules from scratch

A from-scratch **symbolic agent** for the [ARC-AGI-3](https://arcprize.org/) interactive reasoning benchmark.
Every game is an unknown puzzle on a 64×64 colour grid; the agent resets its memory for each game and has to
discover the controls, the mechanics and the goal **by acting**.

**Hard constraints (by design):** no LLM · no pretrained model · no human play traces · no memorisation.
Every concept the agent uses — shapes, events, roles, goals — is an *emergent number* computed from the grid
(frequency, geometry, shape signatures), never a human label such as "wall" or "key".

> Guiding idea: *the right move is single, hidden and hard to find — wrong moves are plentiful and visible.
> So eliminate the wrong ones.*

---

## Results (as of 2026-07-25, measured on the public games)

| Component | Result |
|---|---|
| **Wrong-elimination reward** (`denme/strategies2.py`) | Cleared levels in **4 / 25 games** (vc33 → level 2; cd82, tn36, r11l → level 1) — the best level-clearing method of the project |
| **Exploration benchmark** — 13 strategies, 1500 steps × 2 seeds × 3 games | **Go-Explore** ranked first (304 distinct states vs 182 for random) |
| **Rule learning** — Z3 MaxSAT over 192 game-neutral predicates (`denme/solver/`) | 6 / 6 effects learned on vc33, held-out accuracy **0.84 – 0.98**, < 0.2 s each |
| **Goal hypothesis from the first frame**, no actions spent (`denme/goal/goals.py`) | Matched the human-described goal in **4 / 4** games (UNIFY · FIT · OVERLAP · COLLECT) |
| **Meta detection** — counters, hazards, coupled objects (`denme/goal/meta.py`) | **4 / 4** correct |
| **Colour-mapping inference** (`denme/goal/schema.py`) | Recovered the exact mapping φ = {0→8, 2→9} in ft09 from majority consistency alone |
| **Behavioural bisimulation** (`denme/solver/bisim.py`) | 63 % (tn36) and 83 % (r11l) fewer actions than appearance-based state merging |

**Honest limitation.** The wall is *planning*: coordinated multi-step action sequences. 20+ exploration/decision
methods, a VSA/TPR "brain", CEGIS experiment selection (0/4 gain) and a goal-driven agent (0/5 new games) did not
break it. The details — including every failed attempt — are documented in the reports below.

## How it works

```
64×64 grid ──► Shape tokenizer ──► Event tokenizer ──► Role model ──► Rule learner (Z3 MaxSAT)
                (perception.py)     (transition.py)      (RoleModel)     (predicates.py, learn.py)
                                                                              │
             Goal hypothesis + meta detection (goals.py, meta.py, schema.py) ─┤
                                                                              ▼
                              Decision: wrong-elimination + Go-Explore backbone (strategies2.py)
```

- **Shape tokenizer** — grid → connected-component objects with scale/mirror-invariant signatures and prototype clusters.
- **Event tokenizer** — numeric effect codes (move / merge / appear / disappear / recolour …), no human names.
- **Role model** — emergent roles from behaviour vectors (background and counters found unlabelled in 3 games).
- **Rule learner** — shortest rule *lists* (DNF) per effect with polarity; `unseparable` is used as a diagnostic signal for hidden state.
- **Wrong elimination** — weights W[context-token, action] start at 1 and only drop (×0.15) on no-effect, revert or game-over, so lessons generalise through context tokens.

## Repository layout

```
agent/            perception, action, transition (event tokens), live observation UI, demos
denme/            experiments: env.py (fast headless env), bench.py, strategies*.py
  goal/           goal hypothesis, meta detection, schema / colour mapping, goal-driven agent
  solver/         predicates, Z3 MaxSAT learner, CEGIS, bisimulation, tests
  infra/          copy of the perception/action/transition stack used by experiments
player/           local game server + per-game human notes (used only for evaluation)
DURUM.md          full status summary            SONUC.md   solver measurements
plan.md           vision + tokenizer architecture  *_gorev.md task specifications
```

Design notes and reports are written in Turkish; code identifiers are in English/Turkish.

## Running

The agent runs on top of the official ARC-AGI-3 toolkit ([ARC-AGI-3-Agents](https://github.com/arcprize/ARC-AGI-3-Agents)),
which is not included here.

```bash
# 1. Install the ARC-AGI-3 toolkit and download the game files, then point the agent to them:
export ENVIRONMENTS_DIR=/path/to/environment_files
export OPERATION_MODE=offline

# 2. Strategy benchmark (13 methods, headless, ~150 steps/s)
cd denme
uv run --project /path/to/ARC-AGI-3-Agents python run_all.py 1500 2

# 3. Rule-learner tests
uv run --project /path/to/ARC-AGI-3-Agents python solver/test_solver.py
```

Dependencies: Python 3.10+, `numpy`, `z3-solver`, and the ARC-AGI-3 toolkit (`arc_agi`, `arcengine`).

## License

[MIT](LICENSE)

---

Built by [Adem Batur](https://github.com/adembtr) · Computer Engineering, Sakarya University
