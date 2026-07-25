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

    def vocabulary(self):
        """Gorulen TUM sekil-kumeleri: kumulatif sikliga gore (en cok ustte).
        Her kume icin temsil sekil + toplam gorulme + renkler."""
        reps = {}   # cluster -> info(ilk token) + renk kumesi
        for t, inf in self.info.items():
            k = inf["cluster"]
            r = reps.setdefault(k, {"kume": k, "mask": inf["mask"], "h": inf["h"],
                                    "w": inf["w"], "boyut": len(inf["mask"]),
                                    "renkler": set(), "token_sayisi": 0})
            r["renkler"].add(inf["color"])
            r["token_sayisi"] += 1
            # en buyuk ornek temsil olsun
            if len(inf["mask"]) > r["boyut"]:
                r.update(mask=inf["mask"], h=inf["h"], w=inf["w"], boyut=len(inf["mask"]))
        out = []
        for k, r in reps.items():
            r["renkler"] = sorted(r["renkler"])
            r["siklik"] = self.cluster_count[k] if k < len(self.cluster_count) else 0
            out.append(r)
        return sorted(out, key=lambda x: -x["siklik"])

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
        self.compounds = ShapeVocab()   # KATMAN-2: bilesik sekiller
        self.events = EventVocab()
        self.step = 0
        self.dead_actions = set()   # bu durumda etkisiz kalan aksiyonlar
        self.last_dead = False
        # ILERI MODEL: (aksiyon, tiklanan-kume) -> {olay-token: sayi}  (ogrenilir)
        self.model = {}

    def record_model(self, action, target_cluster, produced_tokens, hidden=0):
        # anahtar GIZLI-FAZ dahil: ayni tik farkli gizli durumda farkli sonuc verir
        key = (action, target_cluster, hidden)
        d = self.model.setdefault(key, {})
        for t in produced_tokens:
            d[t] = d.get(t, 0) + 1

    ALPHA = 1.0    # Dirichlet onsel (yumusatma): gorulmemis sonuca da olasilik

    def predict(self, action, target_cluster, hidden=0):
        """(aksiyon, kume, gizli-faz) -> [(olay-token, olasilik)]. Dirichlet yumusatmali."""
        d = self.model.get((action, target_cluster, hidden))
        if not d:
            return []
        tot = sum(d.values()) + self.ALPHA
        return [(t, n / tot) for t, n in d.items()]

    def efe(self, action, target_cluster, hidden, value_fn):
        """BEKLENEN SERBEST ENERJI terimleri (olasilik matrisi uzerinden):
          exploit  = Σ P(olay)·deger(olay)      (odul beklentisi — somuru)
          epistemic= ALPHA/(N+ALPHA)            (bilinmeyen kutlesi — bilgi kazanci/kesif)
        Karar = exploit + λ·epistemic. Hic denenmemis -> epistemic=1 (max kesif)."""
        d = self.model.get((action, target_cluster, hidden))
        N = sum(d.values()) if d else 0
        denom = N + self.ALPHA
        exploit = sum((n / denom) * value_fn(t) for t, n in d.items()) if d else 0.0
        epistemic = self.ALPHA / denom          # ne kadar ogrenilecek kaldi
        return exploit, epistemic

    def action_meanings(self):
        """KATMAN-1: her A1..A7 NE YAPAR (ogrenilen). Basit tuslarin (tiklama disi)
        urettigi en sik olay-tokenlar -> aksiyonun anlami."""
        out = {}
        for (a, k, h), d in self.model.items():
            if a == 6:            # tiklama sekle-ozel (katman-2), burada degil
                continue
            agg = out.setdefault(a, {})
            for t, n in d.items():
                agg[t] = agg.get(t, 0) + n
        res = {}
        for a, agg in out.items():
            toks = sorted(agg.items(), key=lambda kv: -kv[1])
            res[a] = [{"token": t, "desc": self.events.info[t]["desc"], "sayi": n}
                      for t, n in toks[:3]]
        return res

    def shape_actions(self):
        """KATMAN-2: hangi SEKLE hangi TIKLAMA ne yapar (ogrenilen)."""
        out = {}
        for (a, k, h), d in self.model.items():
            if a != 6 or k < 0:
                continue
            toks = sorted(d.items(), key=lambda kv: -kv[1])
            out[k] = [{"token": t, "desc": self.events.info[t]["desc"], "sayi": n}
                      for t, n in toks[:2]]
        return out

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
        produced = []
        for c in changes:
            eff, d = c["effect"], c["dir"]
            sb = self.shapes.cluster_of(self.shapes.token(c["before"])) if c["before"] is not None else -1
            sa = self.shapes.cluster_of(self.shapes.token(c["after"])) if c["after"] is not None else -1
            sig = (action_code, eff, sb, sa, d)
            tk = self.events._by_sig.get(sig)
            if tk is not None:
                produced.append((tk, self.events.info[tk]["sayi"]))
        return {"step": self.step, "changes": changes, "yeni_tokenlar": fresh,
                "uretilen": produced, "olu": only_nochange}

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

    # --- goz: TUM sekil sozlugu (kumulatif sikliga gore), ekrandakiler isaretli ---
    def eye_tokens(self, grid):
        objs = P.find_objects(grid)
        # su an ekranda olan kumeler + adet
        now = {}
        for o in objs:
            k = self.shapes.cluster_of(self.shapes.token(o))
            now[k] = now.get(k, 0) + 1
        vocab = self.shapes.vocabulary()   # TUM gorulen kumeler, siklik sirali
        out = []
        for v in vocab:
            out.append({"token": v["kume"],
                        "siklik": v["siklik"],            # kumulatif toplam gorulme
                        "ekranda": now.get(v["kume"], 0), # su an ekranda kac tane
                        "ornek_sayisi": v["token_sayisi"],
                        "renkler": v["renkler"],
                        "boyut": v["boyut"],
                        "mask": v["mask"], "h": v["h"], "w": v["w"]})
        # KATMAN-2: bilesik sekiller (yakin+ayni temel sekiller birlesir)
        comp_now = {}
        for co, nmem in P.find_compounds(grid):
            if nmem < 2:
                continue
            k = self.compounds.cluster_of(self.compounds.token(co))
            comp_now.setdefault(k, {"adet": 0, "uye": nmem})
            comp_now[k]["adet"] += 1
        cvocab = self.compounds.vocabulary()
        comp_out = []
        for v in cvocab:
            comp_out.append({"token": v["kume"], "siklik": v["siklik"],
                             "ekranda": comp_now.get(v["kume"], {}).get("adet", 0),
                             "uye": comp_now.get(v["kume"], {}).get("uye", 0),
                             "renkler": v["renkler"], "boyut": v["boyut"],
                             "mask": v["mask"], "h": v["h"], "w": v["w"]})
        return {"bg": P.background_color(grid), "n": len(objs),
                "kume_sayisi": len(vocab), "sekiller": out,
                "bilesik_sayisi": len(cvocab), "bilesikler": comp_out}

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
    """Her KUME icin davranis profili -> 20-boyut ROL vektoru.
    Rol = P(etki | aksiyon) dagilimi. Isim YOK; vektorler kumelenir (R0,R1,...)."""

    def __init__(self):
        self.b = {}

    def _c(self, k):
        return self.b.setdefault(k, {
            "present": 0, "still": 0, "sizesum": 0, "leveltrig": 0,
            "eff": [0] * 10,                 # etki sayaci (E_*)
            "act_cnt": [0] * 8,              # bu nesne varken aksiyon Ai sayisi
            "act_chg": [0] * 8})             # Ai'de bu nesne DEGISTI sayisi

    def update(self, action, events, present, grid_area, leveled):
        involved = set()
        changed = set()
        for cb, ca, eff in events:
            tgt = cb if cb >= 0 else ca
            involved.update([cb, ca, tgt])
            c = self._c(tgt)
            if 0 <= eff < 10:
                c["eff"][eff] += 1
            if eff != E_NOCHANGE:
                changed.add(tgt)
            if leveled:
                c["leveltrig"] += 1
        a = action if 0 <= action < 8 else 0
        for k, sz in present.items():
            c = self._c(k)
            c["present"] += 1
            c["sizesum"] += sz
            c["act_cnt"][a] += 1
            if k in changed:
                c["act_chg"][a] += 1
            if k not in involved:
                c["still"] += 1

    def vector(self, k, grid_area):
        c = self.b[k]
        p = max(1, c["present"])
        e = c["eff"]
        # 12 agregat olasilik
        agg = [
            e[E_MOVE] / p, e[E_SHRINK] / p, e[E_GROW] / p, e[E_MERGE] / p,
            e[E_APPEAR] / p, e[E_VANISH] / p, e[E_RECOLOR] / p,
            c["still"] / p,                                  # duraganlik
            (c["sizesum"] / p) / grid_area,                  # goreli boyut
            c["leveltrig"] / p,                              # hedef-etkisi
            e[E_WIN] / p, e[E_BACK] / p,
        ]
        # 8 aksiyon-tepki: P(degisim | Ai)
        act = [(c["act_chg"][i] / c["act_cnt"][i]) if c["act_cnt"][i] else 0.0
               for i in range(8)]
        return agg + act                                     # 20 boyut

    # --- ROL = davranis vektorlerinin KUMESI (isim YOK, R0,R1,... kendiliginden) ---
    def cluster_roles(self, grid_area, threshold=0.30):
        """Butun kumelerin davranis vektorlerini kumeler. Benzer davranis -> ayni ROL.
        Hicbirine benzemezse -> YENI rol otomatik. Isim yok, sadece R-numarasi."""
        protos = []           # [vec]
        assign = {}           # cluster(sekil) -> rol_id
        for k in self.b:
            v = self.vector(k, grid_area)
            best_i, best_d = None, 1e9
            for i, pv in enumerate(protos):
                d = P.feature_distance(v, pv)
                if d < best_d:
                    best_d, best_i = d, i
            if best_i is not None and best_d <= threshold:
                assign[k] = best_i
            else:
                protos.append(v)
                assign[k] = len(protos) - 1
        return assign, protos

    def table(self, grid_area):
        assign, protos = self.cluster_roles(grid_area)
        rows = []
        for k in self.b:
            rows.append({"kume": k, "rol": assign[k],   # R-numarasi (isimsiz)
                         "vec": [round(x, 2) for x in self.vector(k, grid_area)],
                         "gozlem": self.b[k]["present"]})
        return sorted(rows, key=lambda r: -r["gozlem"])


# ---------------------------------------------------------------------------
# ODUL + HEDEF — degisim=odul, birlesme=buyuk, kazanma=en buyuk, duragan=CEZA
# ---------------------------------------------------------------------------
class Reward:
    """Odul TOKEN'dir — oyuna gore KENDILIGINDEN olusur, degeri KENDILIGINDEN artar.

    Tek EVRENSEL sinyal = SEVIYE atlama (motor verir). Gerisi ogrenilir:
      - her OLAY-TOKENI'nin bir DEGERI var (baslangicta ~0).
      - kazaninca, kazanmadan onceki son olaylara KREDI dagitilir (eligibility trace,
        yakinlikla sonumlenir). Boylece 'birlesme' gibi olaylar KENDILIGINDEN degerlenir
        (o oyunda kazandirdiysa). Baska oyunda kazandiran BASKA olay degerlenir.
    Evrensel ic sinyaller (oyundan bagimsiz, kesif icin):
      + YENILIK (yeni olay-token bulma)   + duraganlik CEZASI (bos aksiyon)."""

    WIN_BASE = 10.0
    NOVELTY = 0.5
    STAGNATE = -1.0
    TRACE_LEN = 12          # kredi dagitilacak son N olay
    TRACE_DECAY = 0.8

    def __init__(self):
        self.total = 0.0
        self.history = []
        self.value = {}          # olay-token -> [toplam_kredi, sayi]   (OGRENILEN odul)
        self.trace = []          # son olay-tokenlari [(token)]  eligibility
        self.stag_streak = 0

    def event_value(self, token):
        v = self.value.get(token)
        return (v[0] / v[1]) if v and v[1] else 0.0

    def _credit(self, amount):
        """Kazanma odulunu son olaylara geriye dagit (yakinlik sonumlu)."""
        w = 1.0
        for tok in reversed(self.trace[-self.TRACE_LEN:]):
            v = self.value.setdefault(tok, [0.0, 0])
            v[0] += amount * w
            v[1] += 1
            w *= self.TRACE_DECAY

    def score(self, step, action, changes, leveled, went_back,
              win_event_tokens, level, produced):
        prod_tokens = [t for t, _ in produced]
        self.trace.extend(prod_tokens)
        effs = [c["effect"] for c in changes]
        nonzero = [e for e in effs if e != E_NOCHANGE]
        # yenilik (evrensel kesif sinyali)
        novelty = (1.0 / (min(cnt for _, cnt in produced) ** 0.5)) if produced else 0.0
        # OGRENILEN deger: uretilen olaylarin degerleri toplami
        learned = sum(self.event_value(t) for t in prod_tokens)

        if leveled:
            r = self.WIN_BASE * (level + 1)          # evrensel, seviyeyle artar
            why = f"★ KAZANMA (seviye {level})"
            self._credit(r)                          # son olaylari DEGERLE
            self.trace = []
            self.stag_streak = 0
        elif went_back:
            r, why = -2.0, "↩ geri gidis"
            self.stag_streak = 0
        elif not nonzero:
            self.stag_streak += 1
            r = self.STAGNATE * min(3, self.stag_streak)
            why = f"∅ duraganlik ×{self.stag_streak}"
        else:
            r = learned + self.NOVELTY * novelty      # ogrenilen + kesif
            why = (f"öğrenilen {learned:.2f} + yenilik {novelty:.2f}"
                   if learned else f"yenilik ×{novelty:.2f}")
            self.stag_streak = 0
        self.total += r
        self.history.append((step, r, why))
        return round(r, 2), why

    def value_table(self):
        rows = [{"token": t, "deger": round(v[0] / v[1], 2), "sayi": v[1]}
                for t, v in self.value.items() if v[1]]
        return sorted(rows, key=lambda x: -x["deger"])


# ---------------------------------------------------------------------------
# ILISKI — iki nesne/kume arasi (deger, ustunde-hareket, icinde, hizali...)
# ---------------------------------------------------------------------------
class RelationModel:
    """BELIRSIZ (isimsiz) ILISKI tokenizer. Iki kume arasi DAVRANIS vektoru biriktirir,
    sonra vektorleri kumeler -> iliski-tokeni (R0,R1,... kendiliginden, isim YOK).
    Boylece 'yol/uzerinde-gezer/degince-sifirlar' gibi iliskiler ELLE tanimlanmaz,
    davranistan cikar. Gelecekte ne tur iliski olacagini bilmemize gerek yok."""

    # davranis boyutlari (sayac indexleri)
    DIMS = ["deg", "ust_gezer", "uzerinden_gecer", "birlikte_hareket",
            "temas_sifirlar", "temas_birlestirir", "icinde", "hizali", "engeller"]

    def __init__(self):
        self.pair = {}   # (kA,kB) -> {gozlem, <DIMS>...}

    def _p(self, a, b):
        key = (min(a, b), max(a, b))
        return self.pair.setdefault(key, dict(gozlem=0, **{d: 0 for d in self.DIMS}))

    def bump(self, a, b, dim, n=1):
        if a == b:
            return
        self._p(a, b)[dim] += n

    def seen(self, a, b):
        if a != b:
            self._p(a, b)["gozlem"] += 1

    def vector(self, a, b):
        r = self._p(a, b)
        g = max(1, r["gozlem"])
        return [r[d] / g for d in self.DIMS]

    def _cluster(self, vecs, threshold=0.25):
        """Davranis vektorlerini kumele -> iliski-token id (isimsiz)."""
        protos = []
        assign = {}
        for key, v in vecs:
            bi, bd = None, 1e9
            for i, pv in enumerate(protos):
                d = P.feature_distance(v, pv)
                if d < bd:
                    bd, bi = d, i
            if bi is not None and bd <= threshold:
                assign[key] = bi
            else:
                protos.append(v)
                assign[key] = len(protos) - 1
        return assign

    def table(self):
        # yeterince gozlenmis ciftler
        items = [(k, self.vector(*k)) for k, r in self.pair.items() if r["gozlem"] >= 2]
        assign = self._cluster(items)
        out = []
        for (a, b), v in items:
            r = self._p(a, b)
            # baskin davranis (gorsel ipucu, ama token = R-numarasi)
            dom = max(range(len(self.DIMS)), key=lambda i: v[i]) if any(v) else -1
            out.append({"a": a, "b": b, "iliski": assign[(a, b)],
                        "baskin": self.DIMS[dom] if dom >= 0 else "-",
                        "vec": [round(x, 2) for x in v], "gozlem": r["gozlem"]})
        return sorted(out, key=lambda x: (x["iliski"], -x["gozlem"]))


# ---------------------------------------------------------------------------
# DINAMIK — tek kumenin sayi-DIZISINE oruntu (sayac turu)
# ---------------------------------------------------------------------------
class DynamicsModel:
    def __init__(self):
        self.seq = {}   # cluster -> [toplam boyut zaman serisi]

    def observe(self, present):
        for k, sz in present.items():
            self.seq.setdefault(k, []).append(sz)

    def pattern(self, k):
        s = self.seq.get(k, [])
        if len(s) < 4:
            return "?", {}
        d = [s[i + 1] - s[i] for i in range(len(s) - 1)]
        resets = sum(1 for x in d if x < -abs(s[0]) * 0.5 and s[0])
        if all(x <= 0 for x in d) and min(d) < 0:
            return "azalan", {"egim": round(sum(d) / len(d), 2)}
        if resets >= 1 and sum(1 for x in d if x > 0) >= 1:
            return "sayac/sifirlanan", {"reset": resets}
        # periyot
        for p in (2, 3, 4):
            if len(s) >= 2 * p and s[-p:] == s[-2 * p:-p]:
                return f"periyodik({p})", {}
        return "duragan/karma", {}

    def is_counter(self, k):
        """Bu kume SAYAC gibi mi? SADECE net azalan/sifirlanan (periyodik DEGIL —
        cogu sey salinim yaptigi icin periyodik yanlis pozitif verir)."""
        p = self.pattern(k)[0]
        return p in ("azalan", "sayac/sifirlanan")

    def counter_clusters(self):
        return {k for k in self.seq if self.is_counter(k)}

    def table(self):
        return [{"kume": k, "oruntu": self.pattern(k)[0], "n": len(v)}
                for k, v in self.seq.items() if len(v) >= 4]


# ---------------------------------------------------------------------------
# PLAN/ROTA — kazanmaya goturen olay-token dizisi (makro/rota tokeni)
# ---------------------------------------------------------------------------
class PlanMemory:
    def __init__(self):
        self.trajectory = []      # su anki olay-token dizisi
        self.routes = []          # kazanan rotalar [(token dizisi)]

    def push(self, event_tokens):
        self.trajectory.extend(event_tokens)

    def on_win(self):
        if self.trajectory:
            self.routes.append(list(self.trajectory))
        self.trajectory = []

    def on_reset(self):
        self.trajectory = []


# ---------------------------------------------------------------------------
# HEDEF HIPOTEZI — bitirme sartini TAHMIN et, cel celtir, celisirse degistir
# ---------------------------------------------------------------------------
class GoalModel:
    """Insan gibi: oyunun BITIRME sartini tahmin et (hipotez), ona dogru oyna.
    Tek celisen kanit -> hemen degistir. Bulamazsan rastgele -> yeniden hipotez.

    Hipotez = olculebilir bir NICELIK + yon (azalt/artir). Ornek adaylar (genel,
    oyuna ozel DEGIL): bir kumenin adedini azalt/artir, nesne sayisini azalt,
    farkli renk sayisini azalt. Bitirme = levels_completed artmasi."""

    def __init__(self):
        self.hyp = None            # ("min_count",k)/("max_count",k)/("min_obj",)/("min_renk",)
        self.tried = set()
        self.confidence = 0.0

    @staticmethod
    def measure(hyp, counts, ncolors, nobj):
        if hyp is None:
            return 0
        t = hyp[0]
        if t == "min_count":
            return counts.get(hyp[1], 0)
        if t == "max_count":
            return -counts.get(hyp[1], 0)
        if t == "min_obj":
            return nobj
        if t == "min_renk":
            return ncolors
        return 0

    def candidates(self, counts):
        c = [("min_obj",), ("min_renk",)]
        for k in counts:
            if counts[k] >= 2:            # birden fazla -> birlestirilebilir olabilir
                c.append(("min_count", k))
        return [h for h in c if h not in self.tried]

    def pick(self, counts):
        cand = self.candidates(counts)
        # once "birden fazla olan kumeyi azalt" (birlestirme sezgisi), sonra digerleri
        cand.sort(key=lambda h: 0 if h[0] == "min_count" else 1)
        self.hyp = cand[0] if cand else None
        self.confidence = 0.0
        return self.hyp

    def falsify(self):
        """Mevcut hipotez celisti -> at, yenisini secmek uzere isaretle."""
        if self.hyp is not None:
            self.tried.add(self.hyp)
        self.hyp = None


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
