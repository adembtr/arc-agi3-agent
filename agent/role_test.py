#!/usr/bin/env python3
"""role_test.py — ROL tokenizerini gercek oyunda test et.

Oyunu kesif ile oynar, her KUME icin davranis profili biriktirir, sonra
davranistan cikan ROLU yazar (arka plan / yol / sayac / kargo / hareketli...).

  cd ARC-AGI-3-Agents && uv run python ../agent/role_test.py <oyun> <adim>
"""
import os
import sys

os.environ.setdefault("OPERATION_MODE", "offline")
os.environ.setdefault("ENVIRONMENTS_DIR", "/home/adem/Desktop/AGI/environment_files")
os.environ.setdefault("MPLBACKEND", "agg")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P                 # noqa: E402
from action import Hand                 # noqa: E402
from transition import Mind, RoleModel  # noqa: E402


def clusters_of_grid(mind, grid):
    """grid'deki her kume -> toplam boyut."""
    present = {}
    for o in P.find_objects(grid):
        k = mind.shapes.cluster_of(mind.shapes.token(o))
        present[k] = present.get(k, 0) + o.size
    return present


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else "lf52"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    h = Hand(game)
    mind = Mind()
    roles = RoleModel()
    grid_area = 64 * 64
    prev_level = h.last["levels_completed"]

    # basit kesif: yon tuslari + nesnelere tik dongusu
    click_i = 0
    for i in range(steps):
        before = h.last["grid"]
        present = clusters_of_grid(mind, before)
        avail = h.last["available"]
        # aksiyon sec (yon + tik karisik)
        if i % 3 == 0 and 6 in avail:
            objs = [o for o in P.find_objects(before) if o.size <= 60]
            if objs:
                o = objs[click_i % len(objs)]
                click_i += 1
                cy, cx = o.centroid
                act, x, y = 6, int(round(cx)), int(round(cy))
            else:
                act, x, y = (avail[0] if avail else 0), None, None
        else:
            cand = [a for a in (1, 2, 3, 4) if a in avail]
            act, x, y = (cand[i % len(cand)] if cand else (avail[0] if avail else 0)), None, None
        # uygula
        if act == 6:
            obs = h.click(x, y)
        elif act == 0:
            obs = h.reset()
        else:
            obs = h.act(act)
        after = obs["grid"]
        res = mind.observe(act, f"[A{act}]", before, after)
        leveled = obs["levels_completed"] > prev_level
        prev_level = obs["levels_completed"]
        # olaylari kume-cifti olarak topla
        events = []
        for c in res["changes"]:
            cb = mind.shapes.cluster_of(mind.shapes.token(c["before"])) if c["before"] is not None else -1
            ca = mind.shapes.cluster_of(mind.shapes.token(c["after"])) if c["after"] is not None else -1
            events.append((cb, ca, c["effect"]))
        roles.update(act, events, present, grid_area, leveled)
        if obs["state"] in ("GAME_OVER", "WIN"):
            h.reset()

    print(f"=== {game}: {steps} adim sonrasi ROL tablosu ===")
    print("kume | rol            | gozlem | davranis vektoru [dur,yon,tik,birl,say,dog,boy,-,lvl,-]")
    for r in roles.table(grid_area):
        print(f"  K{r['kume']:>2} | {r['rol']:<16s} | {r['gozlem']:>5} | {r['vec']}")


if __name__ == "__main__":
    main()
