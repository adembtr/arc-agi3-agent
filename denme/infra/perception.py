#!/usr/bin/env python3
"""perception.py — ARC-AGI-3 ALGI katmani.

Grid (64x64 tamsayi) -> NESNELER (bagli bilesenler) + ILISKILER.

Insanin "ortada yesil sekiller, turuncu kutu, siyah yol var" demesinin
makine karsiligi. Oyun bilgisi YOK; tamamen geometrik/topolojik.
Isim degil ILISKI ile calisir: ayni_sekil, ayna_mi, donmus_mu, degiyor_mu.
"""
from __future__ import annotations
from collections import Counter, deque
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Nesne
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Obj:
    color: int
    cells: frozenset          # {(r,c), ...}  griddeki mutlak hucreler

    # --- turetilmis ozellikler (lazy degil, __post_init__ ile hesaplaniyor) ---
    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def bbox(self):
        rs = [r for r, _ in self.cells]
        cs = [c for _, c in self.cells]
        return (min(rs), min(cs), max(rs), max(cs))

    @property
    def height(self) -> int:
        r0, _, r1, _ = self.bbox
        return r1 - r0 + 1

    @property
    def width(self) -> int:
        _, c0, _, c1 = self.bbox
        return c1 - c0 + 1

    @property
    def centroid(self):
        n = len(self.cells)
        sr = sum(r for r, _ in self.cells)
        sc = sum(c for _, c in self.cells)
        return (sr / n, sc / n)

    @property
    def norm_mask(self) -> frozenset:
        """Sol-uste kaydirilmis desen (konumdan bagimsiz sekil imzasi)."""
        r0, c0, _, _ = self.bbox
        return frozenset((r - r0, c - c0) for r, c in self.cells)

    @property
    def canonical(self) -> frozenset:
        """Dönme+ayna altinda degismez imza (onbellekli — pahali)."""
        nm = self.norm_mask
        c = _CANON_CACHE.get(nm)
        if c is None:
            best = None
            for m in _dihedral(nm):
                t = tuple(sorted(m))
                if best is None or t < best[0]:
                    best = (t, m)
            c = best[1]
            _CANON_CACHE[nm] = c
        return c


_CANON_CACHE = {}   # norm_mask -> canonical  (dihedral pahali, bir kez hesapla)


# ---------------------------------------------------------------------------
# Sekil donusumleri (dönme/ayna) — ilkel, oyun bilgisi yok
# ---------------------------------------------------------------------------
def _norm(cells):
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, c0 = min(rs), min(cs)
    return frozenset((r - r0, c - c0) for r, c in cells)


def _rot90(cells):
    # (r,c) -> (c, -r)
    return _norm([(c, -r) for r, c in cells])


def _reflect(cells):
    # yatay ayna: (r,c) -> (r,-c)
    return _norm([(r, -c) for r, c in cells])


def _dihedral(mask):
    """8 form: 4 dönme x (kendisi + ayna)."""
    out = []
    cur = _norm(mask)
    for _ in range(4):
        out.append(cur)
        out.append(_reflect(cur))
        cur = _rot90(cur)
    return out


# ---------------------------------------------------------------------------
# Algi: grid -> nesneler
# ---------------------------------------------------------------------------
def background_color(grid) -> int:
    """En sik renk = arka plan (0/beyaz varsayimi DEGIL; oyuna gore degisir)."""
    cnt = Counter(v for row in grid for v in row)
    return cnt.most_common(1)[0][0]


def find_objects(grid, background=None, connectivity=8, split_colors=True):
    """Grid -> Obj listesi.

    connectivity=8 (VARSAYILAN): capraz komsuluk dahil -> zincir gibi capraz
      uzanan bir nesne TEK nesne olarak gorulur (piksel piksel degil, nesne bazli).
    split_colors=True: bitisik AMA ayni renk hucreler bir nesne (renk sinirinda kes).
    background: bu renk nesne sayilmaz (None -> otomatik en sik renk).
    """
    H = len(grid); W = len(grid[0])
    if background is None:
        background = background_color(grid)
    if connectivity == 8:
        nbrs = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                (0, 1), (1, -1), (1, 0), (1, 1)]
    else:
        nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    seen = [[False] * W for _ in range(H)]
    objs = []
    for r in range(H):
        for c in range(W):
            if seen[r][c]:
                continue
            col = grid[r][c]
            if col == background:
                seen[r][c] = True
                continue
            # flood fill (ayni renk)
            q = deque([(r, c)])
            seen[r][c] = True
            cells = []
            while q:
                y, x = q.popleft()
                cells.append((y, x))
                for dy, dx in nbrs:
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and not seen[ny][nx]:
                        if split_colors and grid[ny][nx] != col:
                            continue
                        if not split_colors and grid[ny][nx] == background:
                            continue
                        seen[ny][nx] = True
                        q.append((ny, nx))
            objs.append(Obj(color=col, cells=frozenset(cells)))
    return objs


# ---------------------------------------------------------------------------
# Iliskiler (isim degil, geometri)
# ---------------------------------------------------------------------------
def same_shape(a: Obj, b: Obj) -> bool:
    """Ayni desen (kaydirma disinda birebir)."""
    return a.norm_mask == b.norm_mask


def same_shape_symmetry(a: Obj, b: Obj) -> bool:
    """Dondurup/aynalayinca ayni sekil."""
    return a.canonical == b.canonical


def is_mirror(a: Obj, b: Obj) -> bool:
    """b, a'nin (yatay veya dikey) aynasi mi? (dönme haric)"""
    m = a.norm_mask
    horiz = _reflect(m)
    vert = _norm([(-r, c) for r, c in m])
    return b.norm_mask in (horiz, vert)


def is_rotation(a: Obj, b: Obj) -> bool:
    """b, a'nin 90/180/270 dönmusu mu? (ayna haric)"""
    m = a.norm_mask
    rots = []
    cur = m
    for _ in range(3):
        cur = _rot90(cur); rots.append(cur)
    return b.norm_mask in rots


def features(a: Obj):
    """Sekil icin SABIT-BOYUTLU (10) sayisal ozellik vektoru — eğitimsiz.
    Iki sekil arasi benzerlik bu vektorun mesafesiyle olculur (toggle A≈B)."""
    h, w, s = a.height, a.width, a.size
    m = a.norm_mask
    symh = 1.0 if _reflect(m) == m else 0.0
    symv = 1.0 if _norm([(-r, c) for r, c in m]) == m else 0.0
    cs = a.cells
    per = 0
    for (r, c) in cs:
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (r + dy, c + dx) not in cs:
                per += 1
    fill = s / (h * w) if h * w else 0.0
    aspect = h / w if w else 0.0
    # kosegen simetri
    symd = 1.0 if _norm([(c, r) for r, c in m]) == m else 0.0
    # ust/sol yogunluk
    top = sum(1 for r, c in m if r < h / 2) / s if s else 0.0
    left = sum(1 for r, c in m if c < w / 2) / s if s else 0.0
    rows_used = len(set(r for r, _ in m)) / max(1, h)
    cols_used = len(set(c for _, c in m)) / max(1, w)
    compact = s / max(1, per)                      # dolgunluk (cizgi<->blok)
    return [float(s), float(h), float(w), aspect, fill,
            symh, symv, symd, float(per), per / max(1, s),
            float(h * w), top, left, rows_used, cols_used, compact]  # 16 boyut


_FEAT_CACHE = {}   # norm_mask -> features_shape


def features_shape(a: Obj):
    """KUME icin OLCEK-BAGIMSIZ oznitelik (onbellekli)."""
    m = a.norm_mask
    cached = _FEAT_CACHE.get(m)
    if cached is not None:
        return cached
    h, w = a.height, a.width
    s = a.size
    symh = 1.0 if _reflect(m) == m else 0.0
    symv = 1.0 if _norm([(-r, c) for r, c in m]) == m else 0.0
    symd = 1.0 if _norm([(c, r) for r, c in m]) == m else 0.0
    fill = s / (h * w) if h * w else 0.0
    aspect = h / w if w else 0.0
    rows_used = len(set(r for r, _ in m)) / max(1, h)
    cols_used = len(set(c for _, c in m)) / max(1, w)
    # AYNA-BAGIMSIZ: sol/ust yerine merkeze uzaklik (sagdan-soldan simetrik olur)
    top = abs((sum(1 for r, c in m if r < h / 2) / s if s else 0.0) - 0.5)
    left = abs((sum(1 for r, c in m if c < w / 2) / s if s else 0.0) - 0.5)
    vec = [aspect, fill, symh, symv, symd, rows_used, cols_used, top, left]
    _FEAT_CACHE[m] = vec
    return vec


def feature_distance(va, vb):
    """Iki ozellik vektoru arasi olcekli mesafe (0=ayni)."""
    import math
    # her ozelligi kendi buyuklugune gore olcekle
    tot = 0.0
    for x, y in zip(va, vb):
        d = abs(x - y) / (abs(x) + abs(y) + 1.0)
        tot += d * d
    return math.sqrt(tot)


def _bbox_gap(a: Obj, b: Obj) -> int:
    ar0, ac0, ar1, ac1 = a.bbox
    br0, bc0, br1, bc1 = b.bbox
    dr = max(0, br0 - ar1, ar0 - br1)
    dc = max(0, bc0 - ac1, ac0 - bc1)
    return max(dr, dc)


def find_compounds(grid, gap=3, background=None):
    """KATMAN-2: temel sekilleri YAKINLIK + AYNI-sekil ile grupla -> bilesik nesne.
    Ornegin 3x3 dizili kare -> tek buyuk 'izgara' bilesik sekli. (BPE'nin 2B hali.)
    Doner: [(bilesik_Obj, uye_sayisi)]  — tek uyeliler de dahil."""
    objs = find_objects(grid, background=background)
    n = len(objs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if objs[i].canonical == objs[j].canonical and _bbox_gap(objs[i], objs[j]) <= gap:
                parent[find(i)] = find(j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(objs[i])
    out = []
    for members in groups.values():
        cells = frozenset().union(*[m.cells for m in members])
        cols = set(m.color for m in members)
        col = members[0].color if len(cols) == 1 else -1
        out.append((Obj(color=col, cells=cells), len(members)))
    return out


def is_symmetric(a: Obj) -> str:
    """Sekil KENDI icinde simetrik mi? -> '', 'yatay', 'dikey', 'yatay+dikey'."""
    m = a.norm_mask
    res = []
    if _reflect(m) == m:
        res.append("yatay")
    if _norm([(-r, c) for r, c in m]) == m:
        res.append("dikey")
    return "+".join(res)


def similar_scaled(a: Obj, b: Obj) -> bool:
    """Ayni sekil ama farkli olcek (buyutulmus/kucultulmus)? Kaba kontrol:
    kutu oranlari ve doluluk orani ayni mi."""
    if a.height * a.width == 0 or b.height * b.width == 0:
        return False
    # ayni en/boy orani ve ayni doluluk (hucre/ kutu alani)
    ra = a.height / a.width
    rb = b.height / b.width
    da = a.size / (a.height * a.width)
    db = b.size / (b.height * b.width)
    return abs(ra - rb) < 1e-6 and abs(da - db) < 1e-6 and a.size != b.size


def touching(a: Obj, b: Obj, connectivity=4) -> bool:
    """Iki nesne degiyor mu (komsu hucre)."""
    if connectivity == 8:
        nbrs = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                (0, 1), (1, -1), (1, 0), (1, 1)]
    else:
        nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    bset = b.cells
    for (r, c) in a.cells:
        for dy, dx in nbrs:
            if (r + dy, c + dx) in bset:
                return True
    return False


def contains(a: Obj, b: Obj) -> bool:
    """a'nin sinir kutusu b'yi tamamen iceriyor mu (cerceve/kap iliskisi)."""
    ar0, ac0, ar1, ac1 = a.bbox
    br0, bc0, br1, bc1 = b.bbox
    return ar0 <= br0 and ac0 <= bc0 and ar1 >= br1 and ac1 >= bc1 and a is not b


# ---------------------------------------------------------------------------
# Ozet (insan-okur)
# ---------------------------------------------------------------------------
def summarize(grid) -> str:
    bg = background_color(grid)
    objs = find_objects(grid, background=bg)
    lines = [f"arka plan renk = {bg}   |   {len(objs)} nesne bulundu"]
    # renk bazli grupla
    by_color = {}
    for o in objs:
        by_color.setdefault(o.color, []).append(o)
    for col in sorted(by_color):
        group = by_color[col]
        sizes = sorted(o.size for o in group)
        lines.append(f"  renk {col:>2}: {len(group)} nesne, boyutlar={sizes}")
    return "\n".join(lines)


if __name__ == "__main__":
    # kucuk kendi-testi
    demo = [
        [0, 0, 0, 0, 0, 0],
        [0, 3, 3, 0, 3, 0],
        [0, 3, 0, 0, 3, 0],
        [0, 0, 0, 0, 3, 0],
        [0, 0, 0, 0, 0, 0],
    ]
    objs = find_objects(demo)
    print(summarize(demo))
    print("nesne sayisi:", len(objs))
    a, b = objs[0], objs[1]
    print("ayni_sekil:", same_shape(a, b),
          "| ayna_mi:", is_mirror(a, b),
          "| ayni_sekil(dönme/ayna):", same_shape_symmetry(a, b))
