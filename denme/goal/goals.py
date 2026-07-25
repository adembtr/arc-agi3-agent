#!/usr/bin/env python3
"""MODUL A — Hedef hipotezi: ILK KAREDEN, AKSIYONSUZ, SADECE GEOMETRIDEN.

Insan izlerinin mekanizasyonu (hedef_gorev.md §1). Insan hicbir odul sinyali
olmadan hedefi ilk karede kuruyor: "iki ozdes sekil ayri duruyor -> birlestir".
Burada da oyle: 5 oyun-notr GEOMETRIK sablon, nesne kumesi uzerinden puanlanir.

Sablonlar (hepsi sayidan hesaplanir, dunya bilgisi YOK, oyun adi YOK):
  T1 UNIFY(A,B)      iki esdeger nesne ayri -> birlesmeli          (m0r0, lf52)
  T2 FIT(A,B)        iki nesne tamamlayici -> ic ice gecmeli       (g50t)
  T3 OVERLAP(A,B)    ayni sekil farkli yer -> ust uste gelmeli     (ar25)
  T4 CONSISTENT(S,L) kucuk desen <-> buyuk dizilim haritasi        (ft09)
  T5 COLLECT(A*)     >=3 esdeger kucuk nesne -> sayi azalmali      (lf52)

Arayuz: hypothesize_goals(objects, grid) -> puana gore GoalHypothesis listesi.
progress() planlayicinin A* sezgiseli olacak (0..1, 1 = hedef).
"""
import sys
import os
from collections import Counter
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))

SMALL = 200          # env.candidates ile ayni kucuk-nesne esigi


@dataclass
class GoalHypothesis:
    name: str                  # "UNIFY" / "FIT" / "OVERLAP" / "CONSISTENT" / "COLLECT"
    predicate: object          # (objects, grid) -> bool   hedef saglandi mi
    progress: object           # (objects, grid) -> float  0..1 ne kadar yakin
    objects: list = field(default_factory=list)
    score: float = 0.0
    alive: bool = True
    detail: str = ""           # insan-okur tani (rapor icin; karar icin DEGIL)


# ---------------------------------------------------------------------------
# yardimcilar — hepsi geometri/aritmetik
# ---------------------------------------------------------------------------
def bg_color(grid):
    c = Counter()
    for row in grid:
        c.update(row)
    return c.most_common(1)[0][0]


def _cdist(a, b):
    # MANHATTAN: 4-yon hareketin dogal metrigi (Oklid, hedef satirina inmeyi
    # "uzaklasma" sayip yerel minimum uretiyordu — ar25 izinde olculdu)
    (ay, ax), (by, bx) = a.centroid, b.centroid
    return abs(ay - by) + abs(ax - bx)


def _sig(o):
    return (o.canonical, o.color)          # esdegerlik: ayni sekil + ayni renk


def _interesting(objects, grid):
    """Hedef adayi nesneler: kucuk, arka-plan-rengi olmayan."""
    bg = bg_color(grid)
    return [o for o in objects if o.size <= SMALL and o.color != bg]


def _find_pair(objects, sig):
    got = [o for o in objects if _sig(o) == sig]
    return got if len(got) >= 2 else None


# ---------------------------------------------------------------------------
# T1 — UNIFY: iki esdeger nesne ayri duruyor
# ---------------------------------------------------------------------------
def _t1_unify(objs, grid):
    out = []
    by_sig = {}
    for o in objs:
        by_sig.setdefault(_sig(o), []).append(o)
    pairs = {s: v for s, v in by_sig.items() if len(v) == 2}   # TAM iki es
    for s, (a, b) in pairs.items():
        d0 = _cdist(a, b)
        if d0 <= 0:
            continue
        # tek-cift = guclu sinyal; cok cift varsa puan bolunur. mesafe ile artar.
        score = (1.0 / len(pairs)) * min(1.0, d0 / 16.0) * min(1.0, a.size / 4.0)

        def make(sig, dd0):
            # kayboluş SADECE "zaten degiyorlardi" ise birlesme sayilir —
            # baska sebeple kaybolma (arkasina girdi/renk degisti) sahte 1.0
            # uretiyordu (olculdu: ar25 t45) ve best_prog kilitleniyordu.
            last = [dd0]
            def prog(objects, grid):
                got = [o for o in _interesting(objects, grid) if _sig(o) == sig]
                if len(got) <= 1:
                    return 1.0 if last[0] <= 3.0 else 0.0
                d = min(_cdist(x, y) for i, x in enumerate(got)
                        for y in got[i + 1:])
                last[0] = d
                return max(0.0, 1.0 - d / max(dd0, 1e-6))
            def pred(objects, grid):
                return prog(objects, grid) >= 0.999
            return pred, prog
        pred, prog = make(s, d0)
        out.append(GoalHypothesis("UNIFY", pred, prog, [a, b], score,
                                  detail=f"2x ayni(sekil,renk={s[1]}) mesafe={d0:.0f}"))
    return out


# ---------------------------------------------------------------------------
# T2 — FIT: iki nesne tamamlayici (kaydirilinca dolu dikdortgen)
# ---------------------------------------------------------------------------
def _fit_shift(a, b):
    """B'yi kaydirip A ile AYRIK + birlesimi ~dolu dikdortgen olan en iyi
    kaydirmayi bul. TUM ortusme-kaydirmalar denenir (kucuk kutular, ucuz)."""
    ar0, ac0, ar1, ac1 = a.bbox
    br0, bc0, br1, bc1 = b.bbox
    acell = set(a.cells)
    best = (0.0, None)
    # B'nin bbox'u A'nin bbox'uyla kesisecek tum kaydirmalar
    for tr in range(ar0 - br1, ar1 - br0 + 1):
        for tc in range(ac0 - bc1, ac1 - bc0 + 1):
            bcell = {(r + tr, c + tc) for (r, c) in b.cells}
            if acell & bcell:
                continue                      # ortusuyor -> tamamlayici degil
            uni = acell | bcell
            rs = [r for r, _ in uni]
            cs = [c for _, c in uni]
            area = (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1)
            fill = len(uni) / area
            if fill > best[0]:
                best = (fill, (tr, tc))
    return best


def _t2_fit(objs, grid):
    out = []
    n = len(objs)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = objs[i], objs[j]
            # benzer boyutlu kutular (tamamlayici parcalar)
            ah, aw = a.height, a.width
            bh, bw = b.height, b.width
            if not (0.5 <= (ah * aw) / max(bh * bw, 1) <= 2.0):
                continue
            if a.size + b.size < 8:
                continue
            fill, shift = _fit_shift(a, b)
            if shift is None or fill < 0.85:   # birlesim ~dolu dikdortgen olmali
                continue                       # (0.85: AYAR.md'ye bak)
            sa, sb = _sig(a), _sig(b)

            def make(sa, sb, dd0):
                last = [dd0]           # kayboluş != ic-ice-gecme; son mesafeye bak
                def prog(objects, grid):
                    ints = _interesting(objects, grid)
                    got_a = [o for o in ints if _sig(o) == sa]
                    got_b = [o for o in ints if _sig(o) == sb]
                    if not got_a or not got_b:
                        return 1.0 if last[0] <= max(a.height, b.height) else 0.0
                    d = min(_cdist(x, y) for x in got_a for y in got_b)
                    last[0] = d
                    return max(0.0, 1.0 - d / max(dd0, 1e-6))
                def pred(objects, grid):
                    return prog(objects, grid) >= 0.999
                return pred, prog
            pred, prog = make(sa, sb, _cdist(a, b))
            out.append(GoalHypothesis(
                "FIT", pred, prog, [a, b], fill,
                detail=f"tamamlayici cift doluluk={fill:.2f} kaydirma={shift}"))
    return out


# ---------------------------------------------------------------------------
# T3 — OVERLAP: ayni sekil (renk farkli olabilir), farkli konum
# ---------------------------------------------------------------------------
def _t3_overlap(objs, grid):
    out = []
    n = len(objs)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = objs[i], objs[j]
            if a.color == b.color:
                continue                       # ayni renk = UNIFY'in isi
            if a.size < 4:
                continue
            if a.norm_mask == b.norm_mask:     # AYNI YONELIM (ayna degil)
                same_orient = True
            elif a.canonical == b.canonical:   # ayna/donmus
                same_orient = False
            else:
                continue
            d0 = _cdist(a, b)
            if d0 <= 0:
                continue
            score = (0.9 if same_orient else 0.45) * min(1.0, a.size / 8.0)
            na, ca = a.norm_mask, a.color
            nb, cb = b.norm_mask, b.color

            def make(na, ca, nb, cb, dd0):
                last = [dd0]           # kayboluş != ortusme; son mesafe kucukse say
                def find(objects, grid):
                    ints = _interesting(objects, grid)
                    ga = [o for o in ints if o.norm_mask == na and o.color == ca]
                    gb = [o for o in ints if o.norm_mask == nb and o.color == cb]
                    return ga, gb
                def prog(objects, grid):
                    ga, gb = find(objects, grid)
                    if not ga or not gb:
                        return 1.0 if last[0] <= 3.0 else 0.0
                    d = min(_cdist(x, y) for x in ga for y in gb)
                    last[0] = d
                    return max(0.0, 1.0 - d / max(dd0, 1e-6))
                def pred(objects, grid):
                    return prog(objects, grid) >= 0.999 or (
                        all(find(objects, grid)) and
                        min(_cdist(x, y) for x in find(objects, grid)[0]
                            for y in find(objects, grid)[1]) < 1.5)
                return pred, prog
            pred, prog = make(na, ca, nb, cb, d0)
            out.append(GoalHypothesis(
                "OVERLAP", pred, prog, [a, b], score,
                detail=f"ayni-sekil renkler=({ca},{cb}) "
                       f"{'ayni-yon' if same_orient else 'ayna'} mesafe={d0:.0f}"))
    return out


# ---------------------------------------------------------------------------
# T4 — CONSISTENT: kucuk desen (S) <-> buyuk dizilim (L) izomorf
# ---------------------------------------------------------------------------
def _rank_layout(points):
    """Noktalari satir/sutun SIRA-duzenine indir (olcekten bagimsiz yapi)."""
    rs = sorted({r for r, _ in points})
    cs = sorted({c for _, c in points})
    ri = {r: i for i, r in enumerate(rs)}
    ci = {c: i for i, c in enumerate(cs)}
    return frozenset((ri[r], ci[c]) for r, c in points), len(rs), len(cs)


def _t4_consistent(objs, grid):
    out = []
    # S adayi: cok-renkli KUCUK bolge olabilir; burada tek-renk nesnelerin
    # kompozisyonu yerine basit hal: kucuk nesne S (hucre sayisi n>=3),
    # sahnede n adet buyukce nesnenin dizilimi S'nin hucre dizilimiyle izomorf.
    for s in objs:
        n = s.size
        if not (3 <= n <= 12):
            continue
        others = [o for o in objs if o is not s and o.size >= n]
        if len(others) < n:
            continue
        s_lay, sr, sc = _rank_layout(s.cells)
        # buyuklerden n'lisini secmek kombinatorik -> pratik: TUM buyukler
        # tam n adetse dogrudan dene
        if len(others) != n:
            continue
        cents = [(round(o.centroid[0]), round(o.centroid[1])) for o in others]
        l_lay, lr, lc = _rank_layout(cents)
        if (sr, sc) != (lr, lc) or s_lay != l_lay:
            continue

        def make(sid):
            def pred(objects, grid):
                return False                   # φ ogrenilmeden bilinemez (Modul C)
            def prog(objects, grid):
                return 0.0
            return pred, prog
        pred, prog = make(id(s))
        out.append(GoalHypothesis(
            "CONSISTENT", pred, prog, [s] + others, 0.8,
            detail=f"desen {sr}x{sc} ({n} hucre) <-> {n} nesne dizilimi izomorf"))
    return out


# ---------------------------------------------------------------------------
# T5 — COLLECT: >=3 esdeger kucuk nesne
# ---------------------------------------------------------------------------
def _t5_collect(objs, grid):
    out = []
    by_sig = {}
    for o in objs:
        by_sig.setdefault(_sig(o), []).append(o)
    for s, v in by_sig.items():
        if len(v) < 3:
            continue
        n0 = len(v)
        score = min(1.0, 0.25 + 0.08 * n0)

        def make(sig, n0):
            def cnt(objects, grid):
                return sum(1 for o in _interesting(objects, grid)
                           if _sig(o) == sig)
            def pred(objects, grid):
                return cnt(objects, grid) < n0
            def prog(objects, grid):
                c = cnt(objects, grid)
                return max(0.0, min(1.0, (n0 - c) / max(n0 - 1, 1)))
            return pred, prog
        pred, prog = make(s, n0)
        out.append(GoalHypothesis(
            "COLLECT", pred, prog, v, score,
            detail=f"{n0} adet esdeger(renk={s[1]}) nesne"))
    return out


# ---------------------------------------------------------------------------
def hypothesize_goals(objects, grid):
    """Puana gore azalan sirali hipotez listesi. Aksiyon YAPMAZ."""
    objs = _interesting(objects, grid)
    hyps = []
    hyps += _t1_unify(objs, grid)
    hyps += _t2_fit(objs, grid)
    hyps += _t3_overlap(objs, grid)
    hyps += _t4_consistent(objs, grid)
    hyps += _t5_collect(objs, grid)
    hyps.sort(key=lambda h: -h.score)
    return hyps


# ===========================================================================
# MODUL A KABUL OLCUMU (§1.5) — ilk kare, aksiyonsuz
# ===========================================================================
EXPECT = {"m0r0": {"UNIFY"}, "g50t": {"FIT"}, "ar25": {"OVERLAP"},
          "lf52": {"UNIFY", "COLLECT"}}


def acceptance():
    sys.path.insert(0, os.path.join(_HERE, ".."))
    from env import Env
    print("=== MODUL A KABUL: ilk-kare hipotezi vs insan hedefi ===")
    ok = 0
    for game, want in EXPECT.items():
        env = Env(game)
        obs = env.observe()
        hyps = hypothesize_goals(obs["objs"], obs["grid"])
        top2 = [h.name for h in hyps[:2]]
        hit = bool(want & set(top2))
        ok += hit
        print(f"  {game}: beklenen={'|'.join(sorted(want))}  ilk2={top2}  "
              f"{'OK' if hit else 'ISKA'}")
        for h in hyps[:3]:
            print(f"      {h.score:.2f}  {h.name:10s} {h.detail}")
    print(f"KABUL: {ok}/4 {'GECTI' if ok == 4 else 'GECEMEDI'}")
    return ok


if __name__ == "__main__":
    acceptance()
