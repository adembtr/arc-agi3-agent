#!/usr/bin/env python3
"""BISIMULASYON — "bir seyi adiyla degil, DAVRANISIYLA tanimla."

0.22 gorunum-esiginin yerine davranissal denklik (partition refinement):

  1. Basla: tum sekil-imzalari TEK blokta
  2. Tekrarla: ayni bloktaki iki imza bir aksiyon altinda FARKLI etki
     gosterdiyse -> blogu bol
  3. Bolunecek sey kalmayinca dur

Cikan bolumleme = oyunun GERCEKTEN ayirt ettigi en kaba tip kumesi.
Veriden. Etiketsiz. ESIKSIZ. Hiperparametre yok.

Kismi gozlem inceligi: cogu imza her aksiyonda denenmemis -> bolumleme GECICI,
kesfettikce incelir (bu kusur degil avantaj: bloklar ayni-W'yi paylasir, bolununce
yeni blok TAZE W alir — yanlis-elemenin "yeni sekil taze" ilkesiyle ayni).

v1 kapsami (durustluk): derinlik-1 davranissal denklik — (aksiyon -> etki-kumesi)
profili. Tam bisimulasyonun "vardiklari durumlar da denk olmali" kosulu yok
(ardil-durum denkligi sonraki adim). Catisma tanimi: iki imza bir aksiyonda
AYRIK etki kumeleri gosterdiyse farkli (kesisim varsa ayni sayilir — ornekleme
gurultusune dayanikli, varsayilan). strict=True: kumeler esit degilse boler.
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))


class Bisim:
    """Imza -> davranis kaydi -> blok bolumlemesi."""

    def __init__(self, strict=False):
        self.strict = strict
        self.sigs = []            # sig anahtari -> indeks (ilk-gorulme sirasi)
        self.sig_idx = {}
        self.beh = {}             # sig_i -> {aksiyon: set(etki)}
        self.blocks = None        # sig_i -> blok id (tembel)
        self.block_ids = {}       # dondurulmus temsilci -> kalici blok id
        self.next_id = 0
        self._dirty = True

    def sig_of(self, obj):
        """Imza = (kanonik-maske, renk). INCE kimlik; bloklar kabalastirir.
        (Konum imzada YOK: ayni gorunum farkli konum ayni imzada birikir;
        konum farki davranista cikarsa yuklem katmani yakalar.)"""
        return (obj.canonical, obj.color)

    def index(self, obj):
        k = self.sig_of(obj)
        if k not in self.sig_idx:
            self.sig_idx[k] = len(self.sigs)
            self.sigs.append(k)
            self._dirty = True
        return self.sig_idx[k]

    def record(self, obj, action, effects):
        """Gozlem: bu imzaya bu aksiyon uygulandi, bu etkiler cikti."""
        i = self.index(obj)
        d = self.beh.setdefault(i, {})
        d.setdefault(action, set()).update(effects)
        self._dirty = True

    # ---------- catisma: iki imza KANITLA farkli mi ----------
    def _conflict(self, i, j):
        bi, bj = self.beh.get(i, {}), self.beh.get(j, {})
        for a in bi.keys() & bj.keys():
            ei, ej = bi[a], bj[a]
            if self.strict:
                if ei != ej:
                    return True
            elif not (ei & ej):                    # AYRIK = kanitli farkli
                return True
        return False

    # ---------- bolumleme (partition refinement) ----------
    def partition(self):
        """sig_i -> blok id. Bloklar KALICI id tasir: bolununce en eski imzayi
        tutan parca id'sini KORUR, digerleri YENI id alir (taze W ilkesi)."""
        if not self._dirty and self.blocks is not None:
            return self.blocks
        n = len(self.sigs)
        # basla: tek blok; catisma kaniti geldikce bol (acgozlu, deterministik)
        groups = [list(range(n))] if n else []
        changed = True
        while changed:
            changed = False
            out = []
            for g in groups:
                if len(g) <= 1:
                    out.append(g)
                    continue
                parts = []                          # acgozlu gruplama: catisan ayri
                for i in g:                         # (ilk-gorulme sirasi = kararli)
                    for p in parts:
                        if not any(self._conflict(i, j) for j in p):
                            p.append(i)
                            break
                    else:
                        parts.append([i])
                if len(parts) > 1:
                    changed = True
                out.extend(parts)
            groups = out
        # kalici id atama
        blocks = {}
        for g in groups:
            rep = min(g)                            # en eski imza temsilci
            if rep not in self.block_ids:
                self.block_ids[rep] = self.next_id
                self.next_id += 1
            for i in g:
                blocks[i] = self.block_ids[rep]
        self.blocks = blocks
        self._dirty = False
        return blocks

    def n_blocks(self):
        b = self.partition()
        return len(set(b.values())) if b else 0


class BisimShapes:
    """ShapeVocab uyumlu adaptor (env.shapes yerine takilir):
    token(obj) -> imza indeksi, cluster_of(token) -> DAVRANIS blogu.
    Esik YOK. Davranis kaydi ajan update'inden beslenir (feed)."""

    def __init__(self, strict=False):
        self.b = Bisim(strict=strict)

    def token(self, obj):
        return self.b.index(obj)

    def cluster_of(self, token):
        return self.b.partition().get(token, token)

    def feed(self, obj, action, effects):
        self.b.record(obj, action, effects)


# ===========================================================================
# AJAN — WrongElimReward, kumeleme = bisimulasyon (0.22 esigi YOK)
# ===========================================================================
def make_bisim_agent(strict=False):
    from strategies2 import WrongElimReward
    import transition as T
    from predicates import SMALL

    class WrongElimBisim(WrongElimReward):
        """Ayni yanlis-eleme; tek fark: sekil kumesi = davranis blogu."""

        def __init__(self, env, mind, seed=0):
            super().__init__(env, mind, seed)
            self.bs = BisimShapes(strict=strict)
            env.shapes = self.bs                   # kumeleme artik bisimulasyon

        def update(self, obs, cand, obs2, res):
            super().update(obs, cand, obs2, res)
            if cand is None:
                return
            eff = {c["effect"] for c in res["changes"]
                   if c["effect"] != T.E_NOCHANGE} or {T.E_NOCHANGE}
            if cand[0] == "click":                 # tiklanan nesnenin davranisi
                for ob in obs["objs"]:
                    if ob.size > SMALL:
                        continue
                    cy, cx = ob.centroid
                    if (int(round(cx)), int(round(cy))) == (cand[3], cand[4]):
                        self.bs.feed(ob, 6, eff)
                        break
            else:                                  # tus: her nesnenin KENDI etkisi
                for ob in obs["objs"]:
                    if ob.size > SMALL:
                        continue
                    cells = set(ob.cells)
                    oeff = set()
                    for c in res["changes"]:
                        b = c.get("before")
                        if b is not None and c["effect"] != T.E_NOCHANGE \
                                and cells & set(b.cells):
                            oeff.add(c["effect"])
                    self.bs.feed(ob, cand[1], oeff or {T.E_NOCHANGE})

    return WrongElimBisim


# ===========================================================================
# KARSILASTIRMA — esik(0.22) vs bisimulasyon: kume sayisi + seviyeye-aksiyon
# ===========================================================================
def compare(games=("vc33", "tn36", "r11l", "cd82"), seeds=(0, 1), max_steps=2000):
    from cegis import run_measure
    from strategies2 import WrongElimReward
    print(f"=== ESIK(0.22) vs BISIMULASYON, {max_steps} adim, tohum={list(seeds)} ===")
    Wb = make_bisim_agent()
    table = {}
    for game in games:
        row = {}
        for name, cls in (("esik", WrongElimReward), ("bisim", Wb)):
            firsts, levels, nclust = [], [], []
            for seed in seeds:
                r = run_measure(cls, game, max_steps, seed)
                firsts.append(r["first"].get(1))
                levels.append(r["max_level"])
            got = [f for f in firsts if f is not None]
            row[name] = {"first1": firsts, "mean": sum(got) / len(got) if got else None,
                         "max_level": max(levels)}
            f1 = ",".join(str(f) if f else "-" for f in firsts)
            print(f"  {game} {name:6s}: sv1@[{f1}] maxsv={max(levels)}", flush=True)
        table[game] = row
    return table


def cluster_counts(games=("vc33", "tn36", "r11l", "cd82"), steps=600):
    """Ayni kesif izinde: esikli kume sayisi vs bisim blok sayisi."""
    import random
    from env import Env
    import transition as T
    from predicates import SMALL
    print(f"=== KUME SAYISI: esik(0.22) vs bisim bloklari ({steps} adim) ===")
    out = {}
    for game in games:
        env = Env(game)                            # env.shapes = esikli ShapeVocab
        bs = Bisim()
        rng = random.Random(0)
        obs = env.reset()
        for t in range(steps):
            if obs["state"] == "GAME_OVER":
                obs = env.reset()
                continue
            cands = env.candidates(obs)
            if not cands:
                obs = env.step("press", obs["avail"][0] if obs["avail"] else 0)
                continue
            cd = rng.choice(cands)
            obs2 = env.step(cd[0], cd[1], cd[3], cd[4])
            changes = T.diff(obs["grid"], obs2["grid"])
            if cd[0] == "click":
                eff = {c["effect"] for c in changes
                       if c["effect"] != T.E_NOCHANGE} or {T.E_NOCHANGE}
                for ob in obs["objs"]:
                    if ob.size > SMALL:
                        continue
                    cy, cx = ob.centroid
                    if (int(round(cx)), int(round(cy))) == (cd[3], cd[4]):
                        bs.record(ob, 6, eff)
                        break
            else:
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
                    bs.record(ob, cd[1], oeff or {T.E_NOCHANGE})
            obs = obs2
        esik = len(env.shapes.clusters)            # ShapeVocab prototip sayisi
        out[game] = {"esik": esik, "bisim": bs.n_blocks(), "imza": len(bs.sigs)}
        print(f"  {game}: imza={len(bs.sigs)}  esik-kume={esik}  "
              f"bisim-blok={bs.n_blocks()}", flush=True)
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "counts"
    if mode == "counts":
        cluster_counts()
    else:
        compare(max_steps=int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
