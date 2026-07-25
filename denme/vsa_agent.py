#!/usr/bin/env python3
"""VSA AJAN — hiyerarsik bilgi + tek-atis kural + tahmin-tabanli karar.

Her adim:
  1) grid -> nesneler -> SAHNE vektoru (piksel->sekil->nesne->sahne)
  2) aksiyon uygula, yeni sahne gor
  3) KURAL ogren tek-atista: (aksiyon, sahne_once) -> sahne_sonra
  4) KARAR: her aday aksiyon icin SONRA'yi TAHMIN et; hedefe (az nesne / yeni durum)
     goturecegini ONGORENI sec. Model-tabanli akil — arama degil.
  + yanlis-eleme W (etkisiz aksiyonu kapat) korunur.

Sifirdan, ezbersiz, her oyunda yeni vektorler. Metin/LLM/gradyan YOK.
"""
import sys
sys.path.insert(0, "infra")
import numpy as np
import vsa
from knowledge import Knowledge
from strategies import Base


class VSAAgent(Base):
    BETA = 0.15                # yanlis-eleme carpani

    def __init__(self, env, mind, seed=0):
        super().__init__(env, mind, seed)
        self.K = Knowledge()
        self.W = {}            # (aksiyon, sekil-token) -> [0..1] canli/elenmis
        self.seen = set()
        self.scene_cache = None

    def _scene(self, obs):
        objs = []
        for ob in obs["objs"]:
            if ob.size > 200:
                continue
            k = self.mind.shapes.cluster_of(self.mind.shapes.token(ob))
            cy, cx = ob.centroid
            objs.append(self.K.obj(k, ob.color, int(cy), int(cx)))
        return self.K.scene(objs)

    def _ident(self, cd):
        return (6, cd[2]) if cd[0] == "click" else (cd[1], -1)

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        scene_before = self._scene(obs)
        self.scene_cache = scene_before

        def score(cd):
            ident = self._ident(cd)
            w = self.W.get(ident, 1.0)
            if w < 0.05:                          # elenmis -> neredeyse asla
                return -2.0 + self.rng.random() * 0.01
            a = cd[1]
            novelty = 1.0 / (self._count(obs["fp"], cd) + 1)
            # MODEL-TABANLI plan: tahmini SONRA cok mu degistiriyor (umut) — ZAYIF katki
            plan_val = 0.0
            pred = self.K.predict_after(a, scene_before)
            if pred is not None:
                plan_val = max(0.0, 1.0 - vsa.sim(pred, scene_before))
            # KESIF onder (novelty), plan zayif rehber
            return w * (novelty + 0.3 * plan_val) + self.rng.random() * 0.08
        return max(c, key=score)

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        if cand is None or cand[1] == 0:
            return
        scene_before = self.scene_cache if self.scene_cache is not None else self._scene(obs)
        scene_after = self._scene(obs2)
        a = cand[1]
        # KURAL tek-atista ogren: (aksiyon, once) -> sonra
        self.K.learn_rule(a, scene_before, scene_after)
        # yanlis-eleme — SADECE gercekten olu (etkisiz VE durum degismedi) hamleyi kir.
        # yeni durum acan hamleyi ASLA elese (uzun-dizi dogru hamleyi koru).
        ident = self._ident(cand)
        structural = any(ch["effect"] != 0 for ch in res["changes"])
        changed = obs2["fp"] != obs["fp"]
        game_over = obs2["state"] == "GAME_OVER"
        new_state = obs2["fp"] not in self.seen
        if game_over:
            self.W[ident] = self.W.get(ident, 1.0) * self.BETA
        elif not structural:                      # etki yok = yanlis -> kir
            self.W[ident] = self.W.get(ident, 1.0) * self.BETA
        elif not new_state:                       # gorulen duruma dondu -> hafif kir
            self.W[ident] = self.W.get(ident, 1.0) * 0.6
        self.seen.add(obs2["fp"])
        if obs2["level"] > obs["level"]:          # seviye atladi -> revive
            for i in list(self.W):
                self.W[i] = min(1.0, self.W[i] * 4.0)
            self.seen = set()


if __name__ == "__main__":
    import bench
    print("=== VSA AJAN — cesitli oyunlar, 2000 adim ===")
    gec = 0
    for game in ["vc33", "lf52", "m0r0", "cd82", "tn36", "r11l", "g50t", "ft09"]:
        best = 0
        for seed in [0, 1]:
            m = bench.run(VSAAgent, game, 2000, seed=seed)
            best = max(best, m["max_level"])
        gec += best > 0
        print(f"  {game}: max_seviye={best}{' <<<GECTI' if best>0 else ''}", flush=True)
    print(f"-> {gec} oyun seviye gecti")
