#!/usr/bin/env python3
"""YUKLEM HAVUZU — (durum, aksiyon, odak-nesne) -> sabit uzunlukta boolean vektor.

Oyun-NOTR: hicbir yuklem belirli bir oyuna ozel bilgi icermez. Kume id'leri
oyun icinde sifirdan kesfedilir (ShapeVocab) ve SLOT'lara ilk-gorulme sirasiyla
baglanir (sabit vektor uzunlugu icin). Her oyunda YENI PredicatePool ac.

Arayuz (sartname 2.2):
    pool = PredicatePool()
    pool.predicate_names() -> list[str]          # sabit, N adet
    pool.encode(state, action, focus_obj=None) -> list[bool]   # uzunluk N

state = env.Env.observe() ciktisi: {"grid","objs","clusters","state","level","avail","fp"}
"""
from collections import Counter

MAX_CLUSTER_SLOTS = 32          # oyun ici gorulen kume id'si -> slot (ilk-gorulme sirasi)
SIZE_THRESHOLDS = (4, 16, 64, 256)
NOBJ_THRESHOLDS = (2, 4, 8, 16)
COLORS = tuple(range(16))
ACTIONS = tuple(range(8))
DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
SMALL = 200                     # env.candidates ile ayni "kucuk nesne" esigi


def _names():
    n = []
    n += [f"act_eq_{k}" for k in ACTIONS]
    n += [f"cluster_eq_s{s}" for s in range(MAX_CLUSTER_SLOTS)]
    n += [f"color_eq_{v}" for v in COLORS]
    n += [f"size_lt_{t}" for t in SIZE_THRESHOLDS]
    n += [f"at_border_{d}" for d in ("left", "right", "top", "bottom")]
    for d in DIRS:
        n += [f"neighbor_{d}_color_eq_{v}" for v in COLORS]
    n += [f"neighbor_{d}_empty" for d in DIRS]
    n += ["alone_in_row", "alone_in_col"]
    n += [f"n_objects_lt_{t}" for t in NOBJ_THRESHOLDS]
    n += [f"exists_cluster_s{s}" for s in range(MAX_CLUSTER_SLOTS)]
    n += ["two_same_cluster_adjacent"]
    # sahne renk-durumu (gizli-durum acigini kapatmak icin; oyun-notr):
    # vc33 teshisi: ayni gorunur baglam farkli sonuc -> sahnede HANGI renklerin
    # var oldugu ayirt edici olabilir (aktif renk gostergesi vb.)
    n += [f"exists_color_{v}" for v in COLORS]
    n += ["focus_color_count_gt1", "focus_cluster_count_gt1", "focus_color_eq_bg",
          "focus_is_largest", "focus_is_smallest"]
    return n


NAMES = _names()
N = len(NAMES)
_IDX = {name: i for i, name in enumerate(NAMES)}


def _bg_color(grid):
    """Arka plan = en yaygin renk (oyun-notr tanim)."""
    c = Counter()
    for row in grid:
        c.update(row)
    return c.most_common(1)[0][0]


def _dominant_neighbor(grid, obj, dr, dc):
    """Odak nesnenin d yonundeki bitisik hucrelerinin BASKIN rengi (yoksa None).
    'Yol varsa hareket eder' tipini yakalayan kritik yuklem."""
    h, w = len(grid), len(grid[0])
    cells = obj.cells if isinstance(obj.cells, (set, frozenset)) else set(obj.cells)
    cnt = Counter()
    for r, c in cells:
        rr, cc = r + dr, c + dc
        if 0 <= rr < h and 0 <= cc < w and (rr, cc) not in cells:
            cnt[grid[rr][cc]] += 1
    if not cnt:
        return None
    return cnt.most_common(1)[0][0]


class PredicatePool:
    """Oyun-basina bir havuz (kume-slot kaydi oyun ici buyur, oyunlar arasi TASINMAZ)."""

    def __init__(self):
        self.slot = {}                 # kume id -> slot (0..MAX_CLUSTER_SLOTS-1)

    def predicate_names(self):
        return NAMES

    def _slot_of(self, k):
        if k in self.slot:
            return self.slot[k]
        if len(self.slot) >= MAX_CLUSTER_SLOTS:
            return None                # slotlar doldu -> bu kume kodlanamaz (nadir)
        self.slot[k] = len(self.slot)
        return self.slot[k]

    def _cluster_of(self, state, obj):
        """obj'nin kume id'si (env.observe clusters icinden kimlikle bul)."""
        for k, objs in state["clusters"].items():
            for o in objs:
                if o is obj:
                    return k
        return None

    def encode(self, state, action, focus_obj=None):
        grid = state["grid"]
        h, w = len(grid), len(grid[0])
        p = [False] * N

        # --- aksiyon ---
        if 0 <= action <= 7:
            p[_IDX[f"act_eq_{action}"]] = True

        small = [o for o in state["objs"] if o.size <= SMALL]
        bg = _bg_color(grid)

        # --- sahne geneli ---
        n_obj = len(small)
        for t in NOBJ_THRESHOLDS:
            if n_obj < t:
                p[_IDX[f"n_objects_lt_{t}"]] = True
        for k in state["clusters"]:
            s = self._slot_of(k)
            if s is not None:
                p[_IDX[f"exists_cluster_s{s}"]] = True
        # iki ayni-kume nesne bitisik mi (bbox bosluk <= 1)
        adj = False
        ks = list(state["clusters"].items())
        for k, objs in ks:
            for i in range(len(objs)):
                for j in range(i + 1, len(objs)):
                    a, b = objs[i], objs[j]
                    ar0, ac0, ar1, ac1 = a.bbox
                    br0, bc0, br1, bc1 = b.bbox
                    dr = max(br0 - ar1, ar0 - br1, 0)
                    dc = max(bc0 - ac1, ac0 - bc1, 0)
                    if max(dr, dc) <= 1:
                        adj = True
                        break
                if adj:
                    break
            if adj:
                break
        p[_IDX["two_same_cluster_adjacent"]] = adj

        # sahne renk-durumu
        scene_colors = {o.color for o in small}
        for v in scene_colors:
            if 0 <= v <= 15:
                p[_IDX[f"exists_color_{v}"]] = True

        # --- odak nesne ---
        ob = focus_obj
        if ob is not None:
            k = self._cluster_of(state, ob)
            if k is not None:
                s = self._slot_of(k)
                if s is not None:
                    p[_IDX[f"cluster_eq_s{s}"]] = True
            if 0 <= ob.color <= 15:
                p[_IDX[f"color_eq_{ob.color}"]] = True
            for t in SIZE_THRESHOLDS:
                if ob.size < t:
                    p[_IDX[f"size_lt_{t}"]] = True
            r0, c0, r1, c1 = ob.bbox
            p[_IDX["at_border_left"]] = c0 == 0
            p[_IDX["at_border_right"]] = c1 == w - 1
            p[_IDX["at_border_top"]] = r0 == 0
            p[_IDX["at_border_bottom"]] = r1 == h - 1
            for d, (dr, dc) in DIRS.items():
                v = _dominant_neighbor(grid, ob, dr, dc)
                if v is not None:
                    p[_IDX[f"neighbor_{d}_color_eq_{v}"]] = True
                    p[_IDX[f"neighbor_{d}_empty"]] = v == bg
            # satirda/sutunda yalniz mi (baska kucuk nesne ayni satir/sutun bandinda yok)
            rows = set(range(r0, r1 + 1))
            cols = set(range(c0, c1 + 1))
            alone_r = alone_c = True
            for o in small:
                if o is ob:
                    continue
                orr0, occ0, orr1, occ1 = o.bbox
                if rows & set(range(orr0, orr1 + 1)):
                    alone_r = False
                if cols & set(range(occ0, occ1 + 1)):
                    alone_c = False
            p[_IDX["alone_in_row"]] = alone_r
            p[_IDX["alone_in_col"]] = alone_c
            # odak-sahne iliskisi
            p[_IDX["focus_color_count_gt1"]] = sum(
                1 for o in small if o.color == ob.color) > 1
            if k is not None:
                p[_IDX["focus_cluster_count_gt1"]] = len(
                    state["clusters"].get(k, [])) > 1
            p[_IDX["focus_color_eq_bg"]] = ob.color == bg
            if small:
                mx = max(o.size for o in small)
                mn = min(o.size for o in small)
                p[_IDX["focus_is_largest"]] = ob.size == mx
                p[_IDX["focus_is_smallest"]] = ob.size == mn

        return p


# --- sartname arayuzu (modul-duzeyi; TEK oyunluk kullanim icin) ---
_DEFAULT = PredicatePool()


def predicate_names():
    return _DEFAULT.predicate_names()


def encode(state, action, focus_obj=None):
    return _DEFAULT.encode(state, action, focus_obj)


def describe(p_or_indices):
    """Secili yuklemleri insan-okur yap (log/SONUC icin)."""
    if p_or_indices and isinstance(p_or_indices[0], bool):
        idx = [i for i, v in enumerate(p_or_indices) if v]
    else:
        idx = list(p_or_indices)
    return [NAMES[i] for i in idx]


if __name__ == "__main__":
    print(f"toplam yuklem: {N}")
    for i, name in enumerate(NAMES):
        print(f"{i:4d}  {name}")
