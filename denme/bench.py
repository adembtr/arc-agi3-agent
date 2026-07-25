#!/usr/bin/env python3
"""Benchmark harness. Bir stratejiyi bir oyunda N adim surer, METRIK doner.

Hicbiri seviye gecemeyebilir -> ayirt edici PROXY metrikler:
  - max_level        : ulasilan en yuksek seviye (asil hedef)
  - coverage         : gorulen FARKLI durum (state fp) sayisi  (kesif genisligi)
  - events           : kesfedilen FARKLI olay-token sayisi     (mekanik ogrenme)
  - merges           : birlesme olayi sayisi                   (kritik mekanik)
  - min_obj          : ulasilan en az nesne sayisi             (hedefe yakinlik)
  - best_goal_drop   : hedef-olcumunde en buyuk dusus          (ilerleme)
"""
import time
from env import Env
sys_import = __import__


def run(strategy_cls, game, steps, seed=0):
    from transition import Mind
    env = Env(game)
    mind = Mind()
    # sekil sozlugunu paylas (kume tutarli olsun)
    env.shapes = mind.shapes
    strat = strategy_cls(env, mind, seed=seed)
    obs = env.reset()

    seen_states = set()
    seen_events = set()
    merges = 0
    max_level = 0
    min_obj = 10 ** 9
    start_obj = None
    best_goal_drop = 0.0
    t0 = time.time()

    for i in range(steps):
        cand = strat.choose(obs)
        if cand is None:
            kind, a, x, y = "press", (obs["avail"][0] if obs["avail"] else 0), None, None
        elif len(cand) == 4:
            kind, a, x, y = cand
        else:
            kind, a, k, x, y = cand
        before = obs["grid"]
        obs2 = env.step(kind, a, x, y)
        after = obs2["grid"]
        res = mind.observe(a, f"[A{a}]", before, after)
        strat.update(obs, cand, obs2, res)

        seen_states.add(obs2["fp"])
        for t, _ in res.get("uretilen", []):
            seen_events.add(t)
        for c in res["changes"]:
            from transition import E_MERGE
            if c["effect"] == E_MERGE:
                merges += 1
        max_level = max(max_level, obs2["level"])
        nobj = sum(len(v) for v in obs2["clusters"].values())
        if start_obj is None:
            start_obj = nobj
        min_obj = min(min_obj, nobj)
        best_goal_drop = max(best_goal_drop, (start_obj or 0) - nobj)
        obs = obs2

    dt = time.time() - t0
    return {"max_level": max_level, "coverage": len(seen_states),
            "events": len(seen_events), "merges": merges,
            "min_obj": min_obj if min_obj < 10 ** 9 else 0,
            "goal_drop": best_goal_drop, "sec": round(dt, 1),
            "hiz": round(steps / dt, 1) if dt else 0}


def score_metrics(m):
    """Tek skor: seviye en agir, sonra birlesme, hedef-dusus, kapsam, olay."""
    return (m["max_level"] * 1000 + m["merges"] * 20 + m["goal_drop"] * 10
            + m["coverage"] * 0.1 + m["events"] * 1.0)
