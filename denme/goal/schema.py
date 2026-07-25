#!/usr/bin/env python3
"""MODUL C — Seviye semasi: TASINIR sema vs SIFIRLANAN baglama.

SEMA (seviyeler arasi TASINIR):
  - hedef sablonu kimligi (UNIFY/FIT/OVERLAP/CONSISTENT/COLLECT) -> template_bonus
  - tehlike aksiyonlari, baglasiklik, makro kaliplari (meta zaten oyun-omru boyu)
BAGLAMA (her seviyede SIFIRLANIR ve YENIDEN TURETILIR):
  - renk <-> anlam eslemesi (φ bijeksiyonu)  <- ft09'un insani 1-2 seviye yiyen kismi
  - hangi somut nesne hedef/engel, konum bilgisi (hipotezler yeni karede kurulur)

φ yeniden turetme (§3.4): once onceki seviyenin φ'si; K adim ilerleme yoksa
SIRADAKI bijeksiyon (kucuk arama: renk-sayisi! kadar, MDL sirali = az-degisiklik
onde). Yeniden turetme SIFIRDAN OGRENME DEGIL — sema (sablon+mekanik) durur.

CONSISTENT (ft09 tipi) somut hali:
  - renk-agnostik bilesik bolgeler (find_objects split_colors=False) icinde
    >=4 tek-renk alt-blok olanlar; ayni alt-blok sayisi + ayni SIRA-duzeni
    (rank-layout izomorf) olan bolgeler bir AILE olusturur.
  - Aile icinde COGUNLUK = tahtalar, renk-kumesi FARKLI olan tekil = HARITA.
  - Hedef: her tahta[i] = φ(harita[i])  (alt-blok bazinda renk eslemesi)
  - progress(φ) = eslesen alt-blok orani. Tiklama alt-blok rengini dongudurur
    (mekanik OGRENILIR, sabit degil — tik sonrasi progress degisimi izlenir).
"""
import sys
import os
from collections import Counter
from itertools import permutations

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))

import perception as P                     # noqa: E402
from goals import bg_color, GoalHypothesis  # noqa: E402
from goal_agent import GoalAgent           # noqa: E402


# ---------------------------------------------------------------------------
# CONSISTENT tespiti (geometrik, oyun-notr)
# ---------------------------------------------------------------------------
def _rank_layout(points):
    rs = sorted({r for r, _ in points})
    cs = sorted({c for _, c in points})
    ri = {r: i for i, r in enumerate(rs)}
    ci = {c: i for i, c in enumerate(cs)}
    return tuple(sorted((ri[r], ci[c]) for r, c in points))


def find_consistent(grid):
    """KARO-ORGU surumu (ft09 gercek yapisiyla dogrulandi, ama geometrik/notr):
    1) baskin boyutta TAM-dolu tek-renk kareler (karolar) bul
    2) yakinlik orgusuyle GRUPLARA ayir (orgu adimi = karo+bosluk)
    3) her grubun orgusunde EKSIK/kompozit hucre = o grubun HARITASI;
       harita alt-bloklari (kaba-ornekleme) grubun karo-dizilimiyle izomorf
    4) φ COGUNLUKTAN CIKARILIR: tamamen tutarli gruplar φ'yi tanimlar
    -> None | {"gruplar": [ {karolar: {(i,j):renk}, harita: {(i,j):renk}} ],
               "harita_renkleri", "karo_renkleri"}"""
    objs = P.find_objects(grid)
    full = [o for o in objs
            if o.height >= 3 and o.height == o.width
            and o.size == o.height * o.width]
    if len(full) < 8:
        return None
    size_class = Counter(o.height for o in full).most_common(1)[0][0]
    tiles = [o for o in full if o.height == size_class]
    if len(tiles) < 8:
        return None
    # orgu adimi: en yakin komsu mesafesi
    cents = [(o.bbox[0], o.bbox[1]) for o in tiles]
    def d(a, b):
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    pitches = []
    for i, ci in enumerate(cents):
        nn = min((d(ci, cj) for j, cj in enumerate(cents) if j != i),
                 default=None)
        if nn:
            pitches.append(nn)
    if not pitches:
        return None
    pitch = Counter(pitches).most_common(1)[0][0]
    # gruplama (union-find, esik 1.6 x adim)
    parent = list(range(len(tiles)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(len(tiles)):
        for j in range(i + 1, len(tiles)):
            if d(cents[i], cents[j]) <= pitch * 1.6:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(tiles)):
        groups.setdefault(find(i), []).append(i)
    out_groups = []
    map_colors, tile_colors = set(), set()
    for g in groups.values():
        if len(g) < 4:
            continue
        rs = sorted({cents[i][0] for i in g})
        cs = sorted({cents[i][1] for i in g})
        ri = {r: k for k, r in enumerate(rs)}
        ci = {c: k for k, c in enumerate(cs)}
        karolar = {}
        for i in g:
            karolar[(ri[cents[i][0]], ci[cents[i][1]])] = tiles[i].color
            tile_colors.add(tiles[i].color)
        # orgudeki BOS hucre(ler) = harita adayi: grid'den kaba-ornekle oku
        nr, nc = len(rs), len(cs)
        holes = [(a, b) for a in range(nr) for b in range(nc)
                 if (a, b) not in karolar]
        if len(holes) != 1:
            continue
        hr, hc = holes[0]
        r0, c0 = rs[hr] if hr < len(rs) else None, cs[hc] if hc < len(cs) else None
        if r0 is None or c0 is None:
            continue
        # harita = size_class x size_class bolgeyi (nr x nc)'ye kaba-ornekle
        harita = {}
        step_r = size_class / nr
        step_c = size_class / nc
        for a in range(nr):
            for b in range(nc):
                rr = int(r0 + (a + 0.5) * step_r)
                cc = int(c0 + (b + 0.5) * step_c)
                if 0 <= rr < len(grid) and 0 <= cc < len(grid[0]):
                    harita[(a, b)] = grid[rr][cc]
        for (a, b), col in harita.items():
            if (a, b) != (hr, hc):
                map_colors.add(col)
        out_groups.append({"karolar": karolar, "harita": harita,
                           "merkez": (hr, hc)})
    if len(out_groups) < 2:
        return None
    return {"gruplar": out_groups,
            "harita_renkleri": frozenset(map_colors),
            "karo_renkleri": frozenset(tile_colors)}


def infer_phi(cons):
    """φ'yi TAMAMEN-tutarli gruplardan CIKAR (sayim): harita-rengi -> karo-rengi.
    En cok grubu aciklayan tutarli bijeksiyon; yoksa None."""
    votes = Counter()
    for g in cons["gruplar"]:
        pairs = {}
        ok = True
        for (a, b), mcol in g["harita"].items():
            if (a, b) == g["merkez"]:
                continue
            tcol = g["karolar"].get((a, b))
            if tcol is None:
                continue
            if mcol in pairs and pairs[mcol] != tcol:
                ok = False
                break
            pairs[mcol] = tcol
        if ok and pairs and len(set(pairs.values())) == len(pairs):
            votes[tuple(sorted(pairs.items()))] += 1
    if not votes:
        return None
    return dict(votes.most_common(1)[0][0])


def phi_candidates(map_colors, board_colors):
    """Bijeksiyon adaylari, MDL sirali: ortak renkleri SABIT tutan (az degisiklik)
    esleme once, sonra digerleri."""
    mc, bc = sorted(map_colors), sorted(board_colors)
    cands = []
    for perm in permutations(bc, len(mc)):
        phi = dict(zip(mc, perm))
        fixed = sum(1 for k, v in phi.items() if k == v)
        cands.append((-fixed, phi))
    cands.sort(key=lambda t: t[0])
    return [phi for _, phi in cands]


def consistent_progress(grid, phi):
    """φ altinda eslesen (harita-hucre -> karo) orani. Yeni find_consistent
    sozlugu: her grup {karolar:{(i,j):renk}, harita:{(i,j):renk}, merkez}."""
    c = find_consistent(grid)
    if c is None or not phi:
        return None
    tot = hit = 0
    for g in c["gruplar"]:
        for (a, b), mcol in g["harita"].items():
            if (a, b) == g["merkez"]:
                continue
            tcol = g["karolar"].get((a, b))
            if tcol is None:
                continue
            tot += 1
            if phi.get(mcol) == tcol:
                hit += 1
    return hit / max(tot, 1)


# ---------------------------------------------------------------------------
# SEMA + BAGLAMA ayrimi — GoalAgent ustune
# ---------------------------------------------------------------------------
class SchemaAgent(GoalAgent):
    """GoalAgent + CONSISTENT/φ baglamasi + acik sema/baglama yasam dongusu.
    GoalAgent zaten: template_bonus (sema), seviye-atlamada _rebuild (baglama
    sifirla+yeniden-turet), meta oyun-omru (sema). Buradaki ek: φ."""
    PHI_STUCK = 25            # K adim ilerleme yoksa siradaki φ

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.phi = None               # aktif bijeksiyon (BAGLAMA)
        self.phi_list = []
        self.phi_i = 0
        self.phi_no_prog = 0
        self.phi_best = 0.0
        self.phi_kept = False         # onceki seviyeden tasinan φ ile mi basladik

    # -- baglama kur: CONSISTENT varsa φ adaylari --
    def _rebuild(self, obs):
        super()._rebuild(obs)
        c = find_consistent(obs["grid"])
        if c is not None:
            mc = sorted(c["harita_renkleri"])
            bc = sorted(c["karo_renkleri"])
            # cikarilabilen φ ilk aday (cogunluktan); sonra MDL-sirali bijeksiyonlar
            inferred = infer_phi(c)
            self.phi_list = phi_candidates(mc, bc)
            if inferred and inferred in self.phi_list:
                self.phi_list.remove(inferred)
            if inferred:
                self.phi_list.insert(0, inferred)
            # SEMA: onceki seviyenin φ'si EN BASA (tasima onceligi)
            if self.phi is not None and self.phi in self.phi_list:
                self.phi_list.remove(self.phi)
                self.phi_list.insert(0, self.phi)
                self.phi_kept = True
            self.phi_i = 0
            self.phi = self.phi_list[0] if self.phi_list else None
            self.phi_no_prog = 0
            self.phi_best = 0.0
            # CONSISTENT hipotezini φ'li progress ile EN USTE koy
            agent = self

            def prog(objects, grid):
                p = consistent_progress(grid, agent.phi) if agent.phi else None
                return 0.0 if p is None else p

            def pred(objects, grid):
                p = prog(objects, grid)
                return p >= 0.999
            h = GoalHypothesis("CONSISTENT", pred, prog, [],
                               2.0 + self.template_bonus.get("CONSISTENT", 0.0),
                               detail=f"φ-ailesi {len(self.phi_list)} aday")
            self.hyps.insert(0, h)
            self.hidx = 0

    # -- φ dongusu: ilerleme yoksa siradaki bijeksiyon --
    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        if self.phi is None or cand is None:
            return
        p = consistent_progress(obs2["grid"], self.phi)
        if p is None:
            return
        if p > self.phi_best + 1e-9:
            self.phi_best = p
            self.phi_no_prog = 0
        else:
            self.phi_no_prog += 1
        if self.phi_no_prog >= self.PHI_STUCK and len(self.phi_list) > 1:
            self.phi_i = (self.phi_i + 1) % len(self.phi_list)
            self.phi = self.phi_list[self.phi_i]      # BAGLAMAYI degistir
            self.phi_no_prog = 0
            self.phi_best = 0.0                       # yeni φ'yle yeniden olc


# ===========================================================================
# MODUL C KABUL (§3.5): ft09 — sv2'ye harcanan aksiyon < sv1
# ===========================================================================
def acceptance(max_steps=3000, seeds=(0, 1)):
    from goal_agent import run_measure
    print(f"=== MODUL C KABUL: ft09 sema tasima ({max_steps} adim) ===")
    ok = None
    for seed in seeds:
        r = run_measure(SchemaAgent, "ft09", max_steps, seed)
        f = r["first"]
        print(f"  tohum{seed}: maxsv={r['max_level']} seviye-adimlari={f} "
              f"{r['stats']}")
        if 2 in f and 1 in f:
            sv1_cost = f[1]
            sv2_cost = f[2] - f[1]
            ok = sv2_cost < sv1_cost
            print(f"    sv1={sv1_cost} aksiyon, sv2={sv2_cost} aksiyon -> "
                  f"{'SEMA TASINIYOR' if ok else 'TASINMIYOR'}")
    if ok is None:
        print("  KABUL OLCULEMEDI: sv2'ye ulasan kosu yok "
              "(sv1 gecilmeden sema-tasima olculemez)")
    return ok


if __name__ == "__main__":
    acceptance(int(sys.argv[1]) if len(sys.argv) > 1 else 3000)
