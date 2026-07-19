#!/usr/bin/env python3
"""transition.py — SAYISAL beyin: sekil-token + olay-token, TEK SEFERDE ogren.

Ilke (kullanicinin tarifi):
  - her sekil bir NESNE, her nesne bir TOKEN (sayi)
  - her OLAY bir token (sayi):  "A6 -> sekil azaldi",  "A5 -> nesne tasindi"
  - TEK SEFERDE ogren (frekans degil): ilk goruste token uret
  - ASLA unutma (kalici)
  - olay, hafiza, sekil = hepsi SAYI  (etiket sadece bizim gozumuz icin)

Diff, nesneleri hucre-ortusmesiyle esler; degisimi sayisal olay koduna cevirir.
"""
from __future__ import annotations
import perception as P

# --- sayisal etki kodlari ---
E_NOCHANGE, E_MOVE, E_SHRINK, E_GROW, E_APPEAR, E_VANISH, E_MERGE, E_RECOLOR = range(8)
E_WIN = 8               # ust-duzey: seviye/oyun bitti (hedef basarildi)
E_BACK = 9              # BASA dondu = geri gidis (A0 gibi) -> tekrarlanmamali
EFFECT_ADI = {0: "etkisiz", 1: "hareket", 2: "azaldi", 3: "buyudu",
              4: "olustu", 5: "kayboldu", 6: "birlesti", 7: "renk-degisti",
              8: "★ SEVIYE/OYUN BITTI", 9: "↩ BASA DONDU (geri)"}
DIR_ADI = {0: "YUKARI", 1: "ASAGI", 2: "SOL", 3: "SAG"}


def _dir_code(dr, dc):
    if abs(dr) >= abs(dc):
        return 1 if dr > 0 else 0      # ASAGI/YUKARI
    return 3 if dc > 0 else 2          # SAG/SOL


# ---------------------------------------------------------------------------
# SEKIL SOZLUGU — canonical geometri -> sayi (tek seferde)
# ---------------------------------------------------------------------------
class ShapeVocab:
    """IKI KATMANLI sekil sozlugu.
    (1) ORNEK-TOKEN: her (sekil, renk, KONUM) kendi tokeni. Birebir aynisi (ayni
        sekil+renk+konum) tekrar gelirse yeni token YOK; konum bile farkliysa YENI token.
    (2) KUME: tokenlari OLCEK-BAGIMSIZ benzerlik esigiyle gruplar. Ayni sekil farkli
        renk -> farkli token, AYNI kume. Ayni sekil farkli olcek -> AYNI kume."""

    def __init__(self, threshold=0.22):
        self.inst = {}         # (norm_mask,color,pos) -> ornek token
        self.info = {}         # token -> {mask,h,w,color,pos,cluster,vec}
        self.clusters = []     # [prototip olcek-bagimsiz vektor]
        self.cluster_count = []
        self._next = 0
        self.threshold = threshold

    def _assign_cluster(self, vec):
        best_i, best_d = None, 1e9
        for i, pv in enumerate(self.clusters):
            d = P.feature_distance(vec, pv)
            if d < best_d:
                best_d, best_i = d, i
        if best_i is not None and best_d <= self.threshold:
            n = self.cluster_count[best_i]
            self.clusters[best_i] = [(a * n + b) / (n + 1)
                                     for a, b in zip(self.clusters[best_i], vec)]
            self.cluster_count[best_i] += 1
            return best_i
        self.clusters.append(list(vec))
        self.cluster_count.append(1)
        return len(self.clusters) - 1

    def token(self, obj) -> int:
        # sekil KONUMU = piksellerin MERKEZI (centroid), merkez piksel
        cy, cx = obj.centroid
        center = (int(round(cy)), int(round(cx)))
        r0, c0, _, _ = obj.bbox
        key = (obj.norm_mask, obj.color, center)
        t = self.inst.get(key)
        if t is not None:
            return t                      # birebir aynisi (ayni merkez) -> ayni token
        vec = P.features_shape(obj)       # olcek-bagimsiz
        cluster = self._assign_cluster(vec)
        t = self._next
        self._next += 1
        self.inst[key] = t
        self.info[t] = {"mask": [[r - r0, c - c0] for (r, c) in obj.cells],
                        "h": obj.height, "w": obj.width, "color": obj.color,
                        "merkez": center, "cluster": cluster, "vec": vec}
        return t

    def cluster_of(self, token):
        return self.info[token]["cluster"] if token in self.info else -1

    def nearest(self, t, topk=1):
        if t not in self.info:
            return []
        va = self.info[t]["vec"]
        out = []
        for u, inf in self.info.items():
            if u == t:
                continue
            out.append((u, P.feature_distance(va, inf["vec"])))
        out.sort(key=lambda ud: ud[1])
        return [(u, round(100 * (1 - min(1, d)))) for u, d in out[:topk]]


# ---------------------------------------------------------------------------
# OLAY SOZLUGU — (aksiyon, etki, renk, yon) -> sayi (tek seferde)
# ---------------------------------------------------------------------------
class EventVocab:
    def __init__(self):
        self._by_sig = {}      # sig -> token
        self.info = {}         # token -> {sig, desc, sayi, ilk_adim, aksiyon}
        self._next = 0

    def token(self, sig, step, action_label, desc=None) -> tuple:
        """sig = sayisal imza. desc = gosterim (verilmezse imzadan). Doner (token, yeni)."""
        t = self._by_sig.get(sig)
        yeni = False
        if t is None:
            t = self._next
            self._next += 1
            self._by_sig[sig] = t
            self.info[t] = {"sig": sig, "desc": desc or str(sig), "sayi": 0,
                            "ilk_adim": step, "aksiyon": action_label}
            yeni = True
        self.info[t]["sayi"] += 1
        self.info[t]["aksiyon"] = action_label
        return t, yeni


# ---------------------------------------------------------------------------
# DIFF — nesneleri hucre-ortusmesiyle esle, sayisal olaylar cikar
# ---------------------------------------------------------------------------
def diff(before_grid, after_grid):
    """Iki grid -> degisim KAYITLARI. Her kayit bir dict:
       {effect, color, dir, before(obj|None), after(obj|None)}.
    before/after nesneleri sekil-token uretmek icin tutulur (sayisal olay)."""
    B = P.find_objects(before_grid)
    A = P.find_objects(after_grid)
    changes = []
    usedA = set()

    for b in B:
        best, bi = 0, None
        for i, a in enumerate(A):
            if i in usedA:
                continue
            inter = len(b.cells & a.cells)
            if inter > best:
                best, bi = inter, i
        if bi is not None:
            a = A[bi]
            usedA.add(bi)
            if b.color != a.color:
                eff, d = E_RECOLOR, None
            elif a.size < b.size:
                eff, d = E_SHRINK, None
            elif a.size > b.size:
                eff, d = E_GROW, None
            elif b.norm_mask == a.norm_mask and b.bbox[:2] != a.bbox[:2]:
                eff = E_MOVE
                d = _dir_code(a.centroid[0] - b.centroid[0],
                              a.centroid[1] - b.centroid[1])
            else:
                continue   # ayni -> olay yok
            changes.append({"effect": eff, "color": b.color, "dir": d,
                            "before": b, "after": a})
        else:
            changes.append({"effect": E_VANISH, "color": b.color, "dir": None,
                            "before": b, "after": None})
    for i, a in enumerate(A):
        if i not in usedA:
            changes.append({"effect": E_APPEAR, "color": a.color, "dir": None,
                            "before": None, "after": a})

    # BIRLESME: ayni renk >=2 kayboldu & >=1 olustu -> tek merge olayi
    van, app = {}, {}
    for c in changes:
        if c["effect"] == E_VANISH:
            van.setdefault(c["color"], []).append(c)
        elif c["effect"] == E_APPEAR:
            app.setdefault(c["color"], []).append(c)
    merged = set()
    for col in list(van):
        if len(van[col]) >= 2 and 1 <= len(app.get(col, [])) < len(van[col]):
            merged.add(col)
    if merged:
        changes = [c for c in changes
                   if not (c["color"] in merged and c["effect"] in (E_VANISH, E_APPEAR))]
        for col in merged:
            res_obj = app[col][0]["after"] if app.get(col) else None
            changes.append({"effect": E_MERGE, "color": col, "dir": None,
                            "before": None, "after": res_obj})

    if not changes:
        changes.append({"effect": E_NOCHANGE, "color": -1, "dir": None,
                        "before": None, "after": None})
    return changes


# ---------------------------------------------------------------------------
# ZIHIN — sekil+olay tokenlari, tek-seferde ogrenir, unutmaz
# ---------------------------------------------------------------------------
class Mind:
    def __init__(self):
        self.shapes = ShapeVocab()
        self.events = EventVocab()
        self.step = 0
        self.dead_actions = set()   # bu durumda etkisiz kalan aksiyonlar
        self.last_dead = False

    def observe(self, action_code, action_label, before_grid, after_grid):
        self.step += 1
        changes = diff(before_grid, after_grid)
        fresh = []
        only_nochange = all(c["effect"] == E_NOCHANGE for c in changes)
        for c in changes:
            eff, d = c["effect"], c["dir"]
            # SAYISAL olay: KUME gecisi (konum-bagimsiz, oyunlar arasi genellenir)
            sb = self.shapes.cluster_of(self.shapes.token(c["before"])) if c["before"] is not None else -1
            sa = self.shapes.cluster_of(self.shapes.token(c["after"])) if c["after"] is not None else -1
            sig = (action_code, eff, sb, sa, d)
            desc = self._numeric_desc(action_code, eff, sb, sa, d)
            tok, yeni = self.events.token(sig, self.step, action_label, desc)
            if yeni:
                fresh.append(tok)
            if eff == E_NOCHANGE:
                self.dead_actions.add(action_code)
            else:
                self.dead_actions.discard(action_code)
        self.last_dead = only_nochange
        return {"step": self.step, "changes": changes,
                "yeni_tokenlar": fresh, "olu": only_nochange}

    @staticmethod
    def _numeric_desc(a, eff, sb, sa, d):
        """Sayisal/simgesel gosterim — insan etiketi YOK."""
        if eff == E_MOVE:
            return f"A{a}: K{sb} ⇒{DIR_ADI.get(d,'?')}"
        if eff == E_MERGE:
            return f"A{a}: ⊕ ▶ K{sa}"
        if eff == E_APPEAR:
            return f"A{a}: +K{sa}"
        if eff == E_VANISH:
            return f"A{a}: −K{sb}"
        if eff == E_NOCHANGE:
            return f"A{a}: ∅"
        return f"A{a}: K{sb} ▶ K{sa}"   # kume gecisi (buyudu/azaldi/renk)

    def record_goal(self, action_code, action_label):
        """Ust-duzey olay: seviye/oyun bitti -> token (oyunlar arasi ayni)."""
        sig = (action_code, E_WIN, -1, -1, None)
        tok, yeni = self.events.token(sig, self.step, action_label, f"A{action_code}: ★ BITTI")
        return tok, yeni

    def record_backward(self, action_code, action_label):
        """Bu aksiyon bizi BASA dondurdu = geri gidis -> token (kacinilmali)."""
        sig = (action_code, E_BACK, -1, -1, None)
        tok, yeni = self.events.token(sig, self.step, action_label, f"A{action_code}: ↩ GERI")
        return tok, yeni

    # --- goz: bu grid'deki sekilleri KUME olarak (benzerlik gorunumu) ---
    def eye_tokens(self, grid):
        objs = P.find_objects(grid)
        clusters = {}    # cluster -> {ornekler:set, renkler:set, adet, temsil token}
        for o in objs:
            t = self.shapes.token(o)
            k = self.shapes.cluster_of(t)
            c = clusters.setdefault(k, {"kume": k, "ornek_token": t, "renkler": set(),
                                        "adet": 0, "boyut": o.size,
                                        "ornekler": set()})
            c["renkler"].add(o.color)
            c["ornekler"].add(t)
            c["adet"] += 1
        out = []
        for k, g in sorted(clusters.items(), key=lambda kv: -kv[1]["adet"]):
            info = self.shapes.info[g["ornek_token"]]
            out.append({"token": k,                      # KUME id
                        "ornek_sayisi": len(g["ornekler"]),   # kac ayri token
                        "renkler": sorted(g["renkler"]),
                        "adet": g["adet"], "boyut": g["boyut"],
                        "mask": info["mask"], "h": info["h"], "w": info["w"],
                        "benzer": None})
        return {"bg": P.background_color(grid), "n": len(objs),
                "kume_sayisi": len(clusters), "sekiller": out[:16]}

    # --- beyin: olay tokenlari (sayisal) ---
    def event_table(self):
        rows = []
        for t, info in sorted(self.events.info.items(),
                              key=lambda kv: (-kv[1]["sayi"], kv[0])):
            rows.append({"token": t, "desc": info["desc"], "sayi": info["sayi"],
                         "ilk_adim": info["ilk_adim"], "aksiyon": info["aksiyon"]})
        return rows


# ---------------------------------------------------------------------------
# ROL MODELI — davranis profilinden rol cikarir (biz etiketlemeden)
# ---------------------------------------------------------------------------
class RoleModel:
    """Her KUME icin davranis profili biriktirir (olaylardan). 10-boyut davranis
    vektoru -> rol. Rol, olayin ustunde 2. derece anlama katmani."""

    def __init__(self):
        self.b = {}    # cluster -> sayaclar

    def _c(self, k):
        return self.b.setdefault(k, {"present": 0, "still": 0, "dirmove": 0,
                                     "clickchg": 0, "merge": 0, "counter": 0,
                                     "appvan": 0, "sizesum": 0, "leveltrig": 0})

    def update(self, action, events, present, grid_area, leveled):
        """events=[(cb,ca,eff)], present={cluster:size}, leveled=bool"""
        involved = set()
        for cb, ca, eff in events:
            tgt = cb if cb >= 0 else ca
            involved.update([cb, ca, tgt])
            c = self._c(tgt)
            if eff == E_MOVE and action in (1, 2, 3, 4):
                c["dirmove"] += 1
            if eff in (E_SHRINK, E_GROW):
                c["counter"] += 1
            if eff == E_MERGE:
                c["merge"] += 1
            if eff in (E_APPEAR, E_VANISH):
                c["appvan"] += 1
            if action == 6 and eff != E_NOCHANGE:
                c["clickchg"] += 1
            if leveled:
                c["leveltrig"] += 1
        for k, sz in present.items():
            c = self._c(k)
            c["present"] += 1
            c["sizesum"] += sz
            if k not in involved:
                c["still"] += 1

    def vector(self, k, grid_area):
        c = self.b[k]
        p = max(1, c["present"])
        return [c["still"] / p, c["dirmove"] / p, c["clickchg"] / p,
                c["merge"] / p, c["counter"] / p, c["appvan"] / p,
                (c["sizesum"] / p) / grid_area, 0.0, c["leveltrig"] / p, 0.0]

    def role(self, k, grid_area):
        v = self.vector(k, grid_area)
        still, dirm, clk, mrg, cnt, apv, sz, _, lvl, _ = v
        if sz > 0.25 and still > 0.7:
            return "arka plan"
        if lvl > 0:
            return "hedef"
        if cnt > 0.25:
            return "sayac"
        if mrg > 0.05:
            return "kargo"
        if dirm > 0.15:
            return "hareketli"
        if clk > 0.2:
            return "secilebilir"
        if still > 0.8:
            return "statik (yol/duvar)"
        return "belirsiz"

    def table(self, grid_area):
        rows = []
        for k in self.b:
            rows.append({"kume": k, "rol": self.role(k, grid_area),
                         "vec": [round(x, 2) for x in self.vector(k, grid_area)],
                         "gozlem": self.b[k]["present"]})
        return sorted(rows, key=lambda r: -r["gozlem"])


if __name__ == "__main__":
    # kucuk test: bir cizgi her adimda azaliyor -> "azaldi" olay tokeni
    m = Mind()
    line = lambda n: [[0] * 8, [0] + [11] * n + [0] * (7 - n)]
    for n in range(5, 2, -1):
        r = m.observe(6, "[A6]", line(n), line(n - 1))
        print("adim", r["step"], "yeni token:", r["yeni_tokenlar"],
              "olu:", r["olu"])
    print("olay tablosu:")
    for row in m.event_table():
        print("  #%d  %s  (%dx)" % (row["token"], row["desc"], row["sayi"]))
