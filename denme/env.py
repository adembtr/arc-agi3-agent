#!/usr/bin/env python3
"""Headless ortam — HTTP/UI yok, hizli. Sifirdan-sembolik altyapiyi kullanir.
Her strateji bunu surer; metrik olcuruz. LLM/insan-izi YOK; saf matematik.
"""
import os
import sys

os.environ.setdefault("OPERATION_MODE", "offline")
os.environ.setdefault("ENVIRONMENTS_DIR", "/home/adem/Desktop/AGI/environment_files")
os.environ.setdefault("MPLBACKEND", "agg")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "infra"))
import perception as P            # noqa: E402
from action import Hand           # noqa: E402


class Env:
    """Tek oyun. reset/step; gozlem = grid + nesneler + kumeler (sifirdan sozluk)."""

    def __init__(self, game, shapes=None):
        self.game = game
        self.hand = Hand(game)
        # sekil sozlugu (kume) — sifirdan, oyuna ozel
        from transition import ShapeVocab
        self.shapes = shapes if shapes is not None else ShapeVocab()
        self.reset()

    def _cl(self, ob):
        return self.shapes.cluster_of(self.shapes.token(ob))

    def observe(self):
        o = self.hand.last
        grid = o["grid"]
        objs = P.find_objects(grid)
        clusters = {}
        for ob in objs:
            if ob.size > 200:
                continue
            k = self._cl(ob)
            clusters.setdefault(k, []).append(ob)
        return {"grid": grid, "objs": objs, "clusters": clusters,
                "state": o["state"], "level": o["levels_completed"],
                "avail": o["available"], "fp": self._fp(grid)}

    @staticmethod
    def _fp(grid):
        return hash(tuple(tuple(row) for row in grid))

    def reset(self):
        self.hand.reset()
        return self.observe()

    def step(self, kind, a, x=None, y=None):
        if kind == "click":
            self.hand.click(x, y)
        elif a == 0:
            self.hand.reset()
        else:
            self.hand.act(a)
        return self.observe()

    def candidates(self, obs):
        """(kind,a,kume,x,y) aday hamleler — TUM basit tuslar + HER kucuk nesneye tik.
        Genel: merkez iskalarsa diye her nesnenin kendi merkezi (kume temsilcisi degil).
        """
        cands = []
        for a in (1, 2, 3, 4, 5, 7):
            if a in obs["avail"]:
                cands.append(("press", a, -1, None, None))
        # HER kucuk/orta nesneye ayri ayri tik (kume degil — konum ayrimi korunur)
        seen_xy = set()
        for ob in obs["objs"]:
            if ob.size > 200:
                continue
            k = self._cl(ob)
            cy, cx = ob.centroid
            xy = (int(round(cx)), int(round(cy)))
            if xy in seen_xy:
                continue
            seen_xy.add(xy)
            cands.append(("click", 6, k, xy[0], xy[1]))
        return cands
