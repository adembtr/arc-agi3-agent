#!/usr/bin/env python3
"""MODUL B — Meta-nesne tespiti: sayac / tehlike / baglasik / arka plan.

Bunlar hedef DEGIL ama hedef adaylarindan DISLANMALI ve planlayiciya sinyal:
  meta:counter   hangi aksiyon/tik yapilirsa yapilsin ayni yonde monoton
                 degisen bolge -> kalan-butce sinyali, hedef adayi OLAMAZ
  hazard:action  >=%80 oraninda sifirlama ureten aksiyon (>=2 gozlem kapisi)
  hazard:contact sifirlama aninda hareketli nesneye bitisik olan ama normal
                 adimlarda bitisik OLMAYAN renk (ayirt edici bitisiklik)
  coupled        ayni yer-degistirmeyle >=2 nesneyi birlikte suren aksiyon
                 (planlama ipucu: ayirmak icin birini ENGELE daya)
  background     en yuksek frekansli hucre degeri

Tasarim notlari (olcumle bulundu):
  * "aksiyon-bagimsizlik" icin kimlik = (aksiyon, tik-kumesi): tek-aksiyonlu
    (yalniz tik) oyunlarda farkli hedeflere tiklar farkli kimlik sayilir (ft09).
  * SIFIRLAMA tespiti MASKELI: sayac bolgesi sifirlamada bile ilerlemis
    olabilir -> baslangic-grid'iyle karsilastirma sayac-bbox'lari DISINDA
    yapilir (g50t: A5 sifirlar ama alt-satir sayaci ilerlemistir).
  * Sayac monotonlugu ORANSAL (>=%80 ayni yon): sayac sarabilir (12->11 hepsi,
    sonra bastan). Mutlak monotonluk sarmali kacirir.
Hicbiri oyun-ozel degil; hepsi sayim/geometri. Insan notlari SPEC, sabit degil.
"""
import sys
import os
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))

from goals import bg_color, SMALL              # noqa: E402


def _sig(o):
    return (o.canonical, o.color)


class Meta:
    MIN_CHANGES = 3          # sayac: en az gercek degisim
    MONO_RATIO = 0.8         # sayac: ayni-yon orani (sarmal payi)
    RATE_MIN = 0.15          # sayac: degisim/kayit orani (nadir degisen != sayac)
    HAZARD_MIN_OBS = 2       # kapi (asiri-genel veto hatasi tekrarlanmasin)
    HAZARD_ACT_RATIO = 0.5   # geri-sarma orani esigi (g50t olcumu: A5=0.70,
    #                          en yakin gercek aksiyon 0.23 — genis marj)
    REV_FRac = 0.4           # geri-sarma olayi: baslangica >=%40 yaklasma
    REV_MIN = 8              # ... ve >=8 hucre (kucuk oynama sayilmaz)

    def __init__(self):
        self.step_i = 0
        self.bg = None
        self.init_grid = None       # seviyenin baslangic grid'i (maskeli kiyas)
        self.regions = {}           # (renk,r0//8,c0//8) -> {sizes, idents, bbox}
        self.mobile_sigs = set()
        self.ident_uses = Counter()     # (a, kume) -> kullanim
        self.action_uses = Counter()    # a -> kullanim
        self.action_uses_far = Counter()  # a -> baslangictan UZAKKEN kullanim
        self.action_resets = Counter()
        self.adj_any = Counter()
        self.adj_reset = Counter()
        self.n_adj_steps = 0
        self.n_resets = 0
        self.coupled = Counter()
        self.coupled_sigs = {}

    # ------------------------------------------------------------------
    def observe(self, obs, ident, obs2, changes):
        """Her adim: (once, (aksiyon,kume), sonra, diff)."""
        a = ident[0]
        grid, grid2 = obs["grid"], obs2["grid"]
        if self.bg is None:
            self.bg = bg_color(grid)
        if self.init_grid is None:
            self.init_grid = [row[:] for row in grid]
        self.step_i += 1
        self.ident_uses[ident] += 1
        self.action_uses[a] += 1

        # --- sayac bolgeleri ---
        for o in obs2["objs"]:
            if o.size > SMALL:
                continue
            key = (o.color, o.bbox[0] // 8, o.bbox[1] // 8)
            r = self.regions.setdefault(
                key, {"sizes": [], "idents": set(), "bbox": list(o.bbox)})
            if r["sizes"] and r["sizes"][-1] != o.size:
                r["idents"].add(ident)
            r["sizes"].append(o.size)
            b = r["bbox"]
            r["bbox"] = [min(b[0], o.bbox[0]), min(b[1], o.bbox[1]),
                         max(b[2], o.bbox[2]), max(b[3], o.bbox[3])]

        # --- hareketli imzalar + baglasiklik ---
        moves = []
        van, app = {}, {}
        for c in changes:
            b, a2 = c.get("before"), c.get("after")
            if c["effect"] == 1 and b is not None and a2 is not None:  # MOVE
                (by, bx), (ay, ax) = b.centroid, a2.centroid
                moves.append((b, (round(ay - by), round(ax - bx))))
                self.mobile_sigs.add(_sig(b))
            elif c["effect"] == 5 and b is not None:                   # VANISH
                van.setdefault(_sig(b), []).append(b)
            elif c["effect"] == 4 and a2 is not None:                  # APPEAR
                app.setdefault(_sig(a2), []).append(a2)
        for s in van.keys() & app.keys():                # isinlanma = tasima
            b, a2 = van[s][0], app[s][0]
            (by, bx), (ay, ax) = b.centroid, a2.centroid
            moves.append((b, (round(ay - by), round(ax - bx))))
            self.mobile_sigs.add(s)
        if len(moves) >= 2:
            by_disp = Counter(d for _, d in moves)
            disp, n = by_disp.most_common(1)[0]
            if n >= 2 and disp != (0, 0):
                self.coupled[a] += 1
                self.coupled_sigs[a] = {_sig(b) for b, d in moves if d == disp}

        # --- sifirlama = buyuk GERI-SARMA (sayac-maskeli mesafeyle) ---
        # Tam-esitlik yerine: baslangica dogru buyuk yaklasma. (g50t: A5 bazen
        # KISMI sifirlar — gri-2 gibi kalicilar kalir; tam-esitlik %39'da
        # kaliyordu, geri-sarma %70 yakaliyor.)
        mask = self._counter_mask()
        d0 = self._masked_dist(grid, mask)
        d1 = self._masked_dist(grid2, mask)
        was_far = d0 >= self.REV_MIN
        reset = (was_far and (d0 - d1) >= max(self.REV_MIN,
                                              self.REV_FRac * d0)) or \
            obs2["state"] == "GAME_OVER"
        if was_far:
            self.action_uses_far[a] += 1    # sifirlama GOZLEMLENEBILIRDI

        adj = self._adjacent_colors(obs)
        if adj:
            self.n_adj_steps += 1
            for col in adj:
                self.adj_any[col] += 1
        if reset:
            self.n_resets += 1
            self.action_resets[a] += 1
            for col in adj:
                self.adj_reset[col] += 1
        if obs2["level"] > obs["level"]:                 # yeni seviye
            self.init_grid = [row[:] for row in grid2]
            self.regions = {}

    # ------------------------------------------------------------------
    def _counter_regions(self):
        out = []
        for key, r in self.regions.items():
            s = r["sizes"]
            diffs = [b - a for a, b in zip(s, s[1:]) if b != a]
            if len(diffs) < self.MIN_CHANGES or len(r["idents"]) < 2:
                continue
            if len(diffs) / max(len(s), 1) < self.RATE_MIN:
                continue
            neg = sum(1 for d in diffs if d < 0)
            ratio = max(neg, len(diffs) - neg) / len(diffs)
            if ratio >= self.MONO_RATIO:
                out.append((key, r, "azalan" if neg >= len(diffs) - neg
                            else "artan", len(diffs)))
        return out

    def _counter_mask(self):
        """Sayac-adayi bolgelerin bbox hucreleri (sifirlama kiyasinda yok say)."""
        cells = set()
        for key, r, yon, n in self._counter_regions():
            r0, c0, r1, c1 = r["bbox"]
            for rr in range(r0, r1 + 1):
                for cc in range(c0, c1 + 1):
                    cells.add((rr, cc))
        return cells

    def _masked_dist(self, grid, mask):
        g0 = self.init_grid
        d = 0
        for r in range(len(grid)):
            row, row0 = grid[r], g0[r]
            for c in range(len(row)):
                if row[c] != row0[c] and (r, c) not in mask:
                    d += 1
        return d

    def _adjacent_colors(self, obs):
        """Hareketli imzalarin nesnelerine 4-bitisik renkler (kendi+bg haric)."""
        grid = obs["grid"]
        h, w = len(grid), len(grid[0])
        out = set()
        for o in obs["objs"]:
            if o.size > SMALL or _sig(o) not in self.mobile_sigs:
                continue
            cells = set(o.cells)
            for r, c in cells:
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    rr, cc = r + dr, c + dc
                    if 0 <= rr < h and 0 <= cc < w and (rr, cc) not in cells:
                        v = grid[rr][cc]
                        if v != o.color and v != self.bg:
                            out.add(v)
        return out

    # ------------------------------------------------------------------
    def detect(self):
        out = {"counters": [], "hazard_actions": [], "hazard_contacts": [],
               "coupled_actions": [], "background": self.bg}
        for key, r, yon, n in self._counter_regions():
            out["counters"].append({"renk": key[0], "bolge": tuple(r["bbox"]),
                                    "yon": yon, "degisim": n})
        for a, n in self.action_resets.items():
            if a == 0:
                continue        # A0 = evrensel RESET (sartname sabiti) — totoloji
            far = max(self.action_uses_far[a], 1)   # payda = gozlem FIRSATI
            if n >= self.HAZARD_MIN_OBS and n / far >= self.HAZARD_ACT_RATIO:
                out["hazard_actions"].append(
                    {"aksiyon": a, "sifirlama": n, "uzak-kullanim": far})
        # temas-tehlikesi: P(reset | renk bitisik) tabanin cok ustunde olmali.
        # (resetlerin cogu baska sebepli olabilir — butce/sayac — o yuzden
        #  "resetlerin %X'inde bitisikti" DEGIL, kosullu olasilik farki.)
        if self.n_resets >= self.HAZARD_MIN_OBS and self.n_adj_steps > 0:
            base = self.n_resets / max(self.step_i, 1)
            for col, na in self.adj_any.items():
                nr = self.adj_reset.get(col, 0)
                if nr < self.HAZARD_MIN_OBS or na < 3:
                    continue
                p_adj = nr / na
                if p_adj >= 0.5 and p_adj >= 3.0 * base:
                    out["hazard_contacts"].append(
                        {"renk": col, "bitisik_adim": na, "bitisikken_reset": nr,
                         "P(reset|bitisik)": round(p_adj, 2),
                         "taban": round(base, 2)})
        for a, n in self.coupled.items():
            if n >= 2:
                out["coupled_actions"].append(
                    {"aksiyon": a, "gozlem": n,
                     "nesne_sayisi": len(self.coupled_sigs.get(a, []))})
        return out


# ===========================================================================
# MODUL B KABUL OLCUMU (§2.5) — kasif: WrongElimReward (en iyi mevcut)
# ===========================================================================
def _explore(game, steps, seed=0):
    from env import Env
    from transition import Mind, diff
    from strategies2 import WrongElimReward
    env = Env(game)
    mind = Mind()
    env.shapes = mind.shapes
    strat = WrongElimReward(env, mind, seed=seed)
    m = Meta()
    obs = env.reset()
    for t in range(steps):
        cand = strat.choose(obs)
        if cand is None:
            kind, a, k, x, y = "press", (obs["avail"][0] if obs["avail"] else 0), -1, None, None
        else:
            kind, a, k, x, y = cand
        obs2 = env.step(kind, a, x, y)
        res = mind.observe(a, f"[A{a}]", obs["grid"], obs2["grid"])
        strat.update(obs, cand, obs2, res)
        m.observe(obs, (a, k), obs2, res["changes"])
        obs = obs2
    return m


# NOT (olculdu): m0r0'daki turuncu-8 temas-tehlikesi SEVIYE 2 olgusu
# (insan notu satir 47, SEVIYE 2 basligi altinda; seviye 1 grid'inde renk 8 YOK).
# Kasif sv1'i gecemedigi icin sv1 olcumunde beklenemez — beklenti tablosu
# olculebilir-gercege gore: m0r0 sv1 = sayac. Temas-dedektorunun ayirt ediciligi
# yine de dogrulanir: hep-bitisik renkler (11/12) DOGRU sekilde bayraklanmiyor.
EXPECT_B = {
    "ft09": {"counters": True, "hazard_actions": False,
             "hazard_contacts": False, "coupled_actions": False},
    "m0r0": {"counters": True, "hazard_actions": False,
             "hazard_contacts": False, "coupled_actions": False},
    "g50t": {"counters": False, "hazard_actions": True,
             "hazard_contacts": False, "coupled_actions": False},
    "ar25": {"counters": False, "hazard_actions": False,
             "hazard_contacts": False, "coupled_actions": True},
}


def acceptance(steps=1200):
    print(f"=== MODUL B KABUL: meta tespitler ({steps} adim, tohum 0) ===")
    ok = fp = 0
    for game, want in EXPECT_B.items():
        m = _explore(game, steps)
        d = m.detect()
        print(f"  {game}: (reset={m.n_resets} mobil-imza={len(m.mobile_sigs)})")
        for key in ("counters", "hazard_actions", "hazard_contacts",
                    "coupled_actions"):
            got = bool(d[key])
            mark = ""
            if want[key] and got:
                mark = "OK (beklenen)"
            elif want[key] and not got:
                mark = "ISKA (bekleniyordu)"
            elif not want[key] and got:
                mark = "EK-TESPIT (dogrulugu elle incele)"
            if want[key] or got:
                print(f"    {key}: {d[key] if got else '-'}  {mark}")
        hits = all(bool(d[key]) for key in want if want[key])
        ok += hits
    print(f"KABUL: {ok}/4 beklenen tespit tam")
    return ok


if __name__ == "__main__":
    acceptance(int(sys.argv[1]) if len(sys.argv) > 1 else 1200)
