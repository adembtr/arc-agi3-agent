#!/usr/bin/env python3
"""GOZLEM TOPLAYICI — kesif kostur, her adimda (p, action, effects) kaydet.

Satir turleri:
  - adim satiri: encode(durum, aksiyon, odak)  odak = tiklanan nesne (A6) / None (tus)
    effects = adimda gerceklesen TUM etki kodlari (+ WIN seviye-atlama, GAMEOVER)
  - nesne satiri (sadece tus aksiyonlarinda): her kucuk nesne odak; effects = O nesnenin
    kendi etkileri (hucre-ortusmesiyle eslenir). "Yol varsa hareket eder" bunlarla ogrenilir.

Deterministik: tohum sabit. Kesif = yenilik (en az denenen (fp,a,kume) adayi).
"""
import random
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))          # denme/
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))  # denme/infra

from env import Env                     # noqa: E402
import transition as T                  # noqa: E402
from predicates import PredicatePool, SMALL  # noqa: E402

E_WIN = T.E_WIN            # 8  (seviye atlandi)
E_GAMEOVER = 10            # ek etiket (transition'da yok; infra'ya DOKUNMUYORUZ)

EFFECT_NAME = dict(T.EFFECT_ADI)
EFFECT_NAME[E_WIN] = "SEVIYE"
EFFECT_NAME[T.E_BACK] = "geri"
EFFECT_NAME[E_GAMEOVER] = "GAMEOVER"


def _focus_of_click(obs, x, y):
    for ob in obs["objs"]:
        if ob.size > SMALL:
            continue
        cy, cx = ob.centroid
        if (int(round(cx)), int(round(cy))) == (x, y):
            return ob
    return None


def collect(game, steps, seed=0, pool=None, env=None, verbose=False):
    """-> (rows, pool, info).  rows[i] = {p, action, effects, step, obj_row}"""
    env = env or Env(game)
    pool = pool or PredicatePool()
    rng = random.Random(seed)
    rows = []
    obs = env.reset()
    tried = {}
    max_level = 0

    for t in range(steps):
        if obs["state"] == "GAME_OVER":                 # olu oyunda oynama -> reset
            obs = env.reset()
            continue
        cands = env.candidates(obs)
        if not cands:
            obs = env.step("press", obs["avail"][0] if obs["avail"] else 0)
            continue

        def cnt(cd):
            return tried.get((obs["fp"], cd[1], cd[2]), 0)
        m = min(cnt(cd) for cd in cands)
        pick = rng.choice([cd for cd in cands if cnt(cd) == m])
        kind, a, k, x, y = pick
        focus = _focus_of_click(obs, x, y) if kind == "click" else None

        obs2 = env.step(kind, a, x, y)
        changes = T.diff(obs["grid"], obs2["grid"])
        step_eff = {c["effect"] for c in changes if c["effect"] != T.E_NOCHANGE}
        if obs2["level"] > obs["level"]:
            step_eff.add(E_WIN)
        if obs2["state"] == "GAME_OVER":
            step_eff.add(E_GAMEOVER)
        if not step_eff:
            step_eff = {T.E_NOCHANGE}

        rows.append({"p": pool.encode(obs, a, focus), "action": a,
                     "effects": frozenset(step_eff), "step": t, "obj_row": False})

        if kind == "press":                             # nesne-duzeyi satirlar
            for ob in obs["objs"]:
                if ob.size > SMALL:
                    continue
                cells = set(ob.cells)
                oeff = set()
                for c in changes:
                    b = c.get("before")
                    if b is not None and c["effect"] != T.E_NOCHANGE \
                            and cells & set(b.cells):
                        oeff.add(c["effect"])
                rows.append({"p": pool.encode(obs, a, ob), "action": a,
                             "effects": frozenset(oeff or {T.E_NOCHANGE}),
                             "step": t, "obj_row": True})

        tried[(obs["fp"], a, k)] = cnt(pick) + 1
        max_level = max(max_level, obs2["level"])
        obs = obs2

    info = {"max_level": max_level, "n_rows": len(rows), "steps": steps}
    return rows, pool, info


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "vc33"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    rows, pool, info = collect(game, steps, seed=0)
    from collections import Counter
    c = Counter()
    for r in rows:
        for e in r["effects"]:
            c[e] += 1
    print(f"{game}: {info['n_rows']} satir / {steps} adim, max_seviye={info['max_level']}")
    for e, n in c.most_common():
        print(f"  etki {e} ({EFFECT_NAME.get(e, '?')}): {n} satir")
