#!/usr/bin/env python3
"""brain_ui.py — Ajani GOZLEMLEME arayuzu.

Orta = oyun.  Sol = GOZ (nesneler/sekiller).  Alt = EL (son aksiyon).
Sag = BEYIN (atomlar — SIFIRDAN baslar, gozledikce dolar).

SPACE = bir clock sinyali: ajan SIRADAKI adimini atar (kesif).
Kullanici grid'e tiklayip / rakam basip kendi de surebilir.

Calistir (arc_agi venv):
  cd ARC-AGI-3-Agents && uv run python ../agent/brain_ui.py
  http://localhost:8001
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P            # noqa: E402
from action import Hand, describe  # noqa: E402
from transition import (Mind, RoleModel, Reward, RelationModel,  # noqa: E402
                        DynamicsModel, PlanMemory, GoalModel, E_MERGE, E_NOCHANGE)

COLOR_MAP = {
    0: "#FFFFFF", 1: "#CCCCCC", 2: "#999999", 3: "#666666",
    4: "#333333", 5: "#000000", 6: "#E53AA3", 7: "#FF7BCC",
    8: "#F93C31", 9: "#1E93FF", 10: "#88D8F1", 11: "#FFDC00",
    12: "#FF851B", 13: "#921231", 14: "#4FCC30", 15: "#A356D6",
}
GAMES = ["lf52", "g50t", "ft09", "m0r0"]

_LOCK = threading.Lock()


class Session:
    """Tek oturum: el + beyin + kesif durumu."""
    def __init__(self, game="lf52"):
        self.start(game)

    def start(self, game):
        self.game = game
        self.hand = Hand(game)
        self.mind = Mind()
        self.rolemodel = RoleModel()   # davranistan ROL cikarimi (20-boyut)
        self.reward = Reward()         # degisim/birlesme/kazanma odulu, duraganlik cezasi
        self.relmodel = RelationModel()  # iki nesne arasi iliski
        self.dynmodel = DynamicsModel()  # sayi-dizisi oruntusu (sayac turu)
        self.plan = PlanMemory()       # kazanan rota (makro token)
        self.act_value = {}            # aksiyon -> ortalama odul (odul-gudumlu kesif)
        self.grid_area = 64 * 64
        self.clicked_shapes = set()    # TIKLANMIS sekil-tokenlari (merak icin)
        self.boring = set()            # YENI olay uretmeyen konum kovalari (tekrarlama)
        self.prev_level = self.hand.last["levels_completed"]
        # HAFIZA: gorulen durumlar (fingerprint) — basa donusu (geri) anlamak icin
        self.start_fp = self._fp(self.hand.last["grid"])
        self.visited = {self.start_fp}
        self.back_actions = set()      # BASA donduren aksiyonlar (kacinilacak)
        # PLANLAYICI durumu
        self.expecting_target = False  # bir kargo tikladik, hedef bekliyoruz
        self.last_appeared = []        # son adimda BELIREN nesne merkezleri (x,y)
        self.last_click = None         # son tiklanan (x,y) — toggle tespiti icin
        self.roles = {}                # renk -> rol ("kargo","araba"...) davranistan
        # GERI-IZLEMELI ARAMA (reset-only DFS, token/yol tabanli — oyuna ozel DEGIL)
        self.path = []                 # islenmis kesif hamleleri [(kind,a,x,y)]
        self.tried = {}                # derinlik -> denenmis (aksiyon,kume) keys
        self.replay = []               # reset sonrasi tekrar oynanacak hamleler
        self._pending_reset = False    # backtrack: once reset et
        self._deadend = False          # son hamle duvara mi tostu
        self._move_type = "fresh"      # fresh / replay / reset
        self._cur_move = None; self._cur_key = None; self._cur_depth = 0
        # GIZLI DURUM takibi (grid ekranda tam durum DEGIL — davranistan cikar)
        self.pending = set()           # aktif "secim/firsat" latenti (doganlar)
        self.has_hidden = False        # ayni grid+aksiyon farkli sonuc -> gizli durum VAR
        self._trans = {}               # (grid_fp,aksiyon,kume) -> gorulen sonuc_fp'leri
        # HEDEF HIPOTEZI + rastgele-kesif durumu
        self.goal = GoalModel()
        self.path_best = None          # bu yolda hedefe en yakin olculen deger
        self.stuck = 0                 # pes pese duvar sayisi
        self.random_burst = 0          # kalan rastgele hamle
        self.last_hand = {"desc": "oyun basladi (RESET)", "touched": None,
                          "action": 0}

    @staticmethod
    def _fp(grid):
        return hash(tuple(tuple(row) for row in grid))

    def hidden_phase(self):
        """Davranistan cikarilan GIZLI DURUM ozeti (secim/firsat latenti).
        Ayni grid farkli fazda farkli davranir -> ileri-model bunu ayirir."""
        return hash(frozenset(self.pending))

    def aug_fp(self, grid):
        """Grid + gizli faz = etkin durum (tekrar/geri-donus dogru anlasilsin)."""
        return (self._fp(grid), self.hidden_phase())

    @staticmethod
    def _appeared(before, after):
        """after'da olup before ile ORTUSMEYEN kucuk nesneler = BELIREN (hedef)."""
        B = P.find_objects(before)
        A = P.find_objects(after)
        out = []
        for a in A:
            if a.size > 40:
                continue
            if not any(len(a.cells & b.cells) > 0 for b in B):
                cy, cx = a.centroid
                out.append((int(round(cx)), int(round(cy))))
        return out

    # --- KARAR BEYNI: deger-tabanli. Her adayin BEKLENEN degerini hesapla, en iyiyi sec.
    #     Deger = ileri-model(olaylar) x ogrenilen-olay-degeri + yenilik(kesif). Elle kural YOK.
    NOVELTY_BONUS = 0.6

    def _ranked_cands(self, grid, avail):
        """Aday hamleler, karar-beyni degeriyle sirali. (kind,a,kume,x,y)."""
        cl = lambda ob: self.mind.shapes.cluster_of(self.mind.shapes.token(ob))
        objs = P.find_objects(grid)
        cands = []
        for a in (1, 2, 3, 4, 5, 7):
            if a in avail and a not in self.back_actions:
                cands.append(("press", a, -1, None, None))
        seen = set()
        for ob in objs:
            if ob.size > 200:
                continue
            k = cl(ob)
            if k in seen:
                continue
            seen.add(k)
            cy, cx = ob.centroid
            cands.append(("click", 6, k, int(round(cx)), int(round(cy))))
        # firsat: son hamlenin yarattigi yeni nesne
        afford = set()
        for (ax, ay) in (self.last_appeared or []):
            for ob in objs:
                if (ay, ax) in ob.cells:
                    afford.add(cl(ob))

        # ON-BILGI (Bayes onseli, oyunda dogrulanir): A5 muhtemelen RESET/tuzak -> caydir
        PRIOR = {5: -1.0, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 7: 0.0}
        LAMBDA = 0.7                        # kesif(bilgi kazanci) agirligi
        hph = self.hidden_phase()          # su anki gizli faz (inanc)
        vfn = self.reward.event_value       # olay -> ogrenilen deger

        def score(c):
            # KARAR = beklenen serbest enerji: exploit(odul) + λ·epistemic(bilgi kazanci)
            kind, a, k, x, y = c
            exploit, epistemic = self.mind.efe(a, k, hph, vfn)
            s = exploit + LAMBDA * epistemic
            if kind == "click" and k in afford:
                s += 1.0                    # firsat (yeni dogan) — zayif onsel
            if kind == "press":
                s += PRIOR.get(a, 0.0)
            return s
        cands.sort(key=score, reverse=True)
        return cands

    def next_explore(self):
        """GERI-IZLEMELI ARAMA (reset-only DFS). Token/yol tabanli, oyuna ozel DEGIL.
        - ilerleme -> yolu uzat (deepen)
        - duvar (duraganlik/GAME_OVER) -> son hamleyi degistir: RESET + prefix REPLAY + alternatif
        """
        o = self.hand.last
        avail, grid, state = o["available"], o["grid"], o["state"]

        # 0) RASTGELE KESIF: cok takildik, hipotezi curuttuk -> birkac rastgele hamle
        #    (insan gibi: bulamayinca rastgele oyna, sonra yeniden plan kur)
        if self.random_burst > 0:
            self.random_burst -= 1
            self._move_type = "fresh"
            objs = P.find_objects(grid)
            small = [ob for ob in objs if ob.size <= 60]
            # aksiyon indeksini adimla degistir (deterministik ama degisken — Math.random yok)
            pick = self.mind.step % max(1, (len(small) + len(avail)))
            if pick < len(avail):
                a = avail[pick]
                self._cur_move = ("press", a, None, None)
            else:
                ob = small[(pick - len(avail)) % len(small)] if small else None
                if ob is None:
                    a = avail[0] if avail else 0
                    self._cur_move = ("press", a, None, None)
                else:
                    cy, cx = ob.centroid
                    self._cur_move = ("click", 6, int(round(cx)), int(round(cy)))
            self._cur_key = (self._cur_move[1], -2)   # rastgele isareti
            self._cur_depth = len(self.path)
            return self._cur_move

        # 1) prefix REPLAY (backtrack sonrasi eski yolu tekrar oyna)
        if self.replay:
            self._move_type = "replay"
            return self.replay.pop(0)
        # 2) son hamle DUVARA tostuysa -> backtrack
        if self._deadend or state == "GAME_OVER":
            self._deadend = False
            return self._backtrack()

        # 3) taze kesif: bu derinlikte DENENMEMIS en iyi adayi sec
        cands = self._ranked_cands(grid, avail)
        d = len(self.path)
        tried = self.tried.setdefault(d, set())
        for c in cands:
            key = (c[1], c[2])              # (aksiyon, kume)
            if key not in tried:
                self._cur_move = ("click", 6, c[3], c[4]) if c[0] == "click" else ("press", c[1], None, None)
                self._cur_key = key
                self._cur_depth = d
                self._move_type = "fresh"
                if c[0] == "click":
                    self.last_click = (c[3], c[4])
                return self._cur_move
        # bu derinlikte deneyecek sey kalmadi -> backtrack
        return self._backtrack()

    def _backtrack(self):
        """Son hamleyi geri al: daha derin denemeleri unut, RESET + prefix REPLAY,
        sonra o derinlikte FARKLI (denenmemis) hamle denenecek."""
        # daha derin denenmis-kumeleri temizle (baska alt-agac)
        for dd in [x for x in self.tried if x > max(0, len(self.path) - 1)]:
            del self.tried[dd]
        if not self.path:
            self.tried.clear()             # bastan tazele
            self._move_type = "reset"
            return ("press", 0, None, None)
        self.path.pop()                    # son hamleyi at
        self.replay = list(self.path)      # prefix'i tekrar oynayacagiz
        self._move_type = "reset"
        return ("press", 0, None, None)    # once RESET (geri-alma yok, bastan)

    def _observe_relations(self, objs_before, changes, went_back, cl):
        """Iki nesne arasi iliskiyi DAVRANISTAN besle (isimsiz tokenizer).
        - hareket eden A'nin gectigi yer B ile cakisir -> A, B'nin uzerinde gezer
        - temas + oyun sifirlandi -> temas_sifirlar ; temas + birlesme -> temas_birlestirir
        - deg/icinde/hizali statik iliskiler."""
        from transition import E_MOVE, E_MERGE
        small = [o for o in objs_before if o.size <= 200]
        # statik iliskiler (cift basina, sinirli)
        for i in range(len(small)):
            for j in range(i + 1, len(small)):
                a, b = small[i], small[j]
                ka, kb = cl(a), cl(b)
                if ka == kb:
                    continue
                self.relmodel.seen(ka, kb)
                if P.touching(a, b):
                    self.relmodel.bump(ka, kb, "deg")
                    if went_back:
                        self.relmodel.bump(ka, kb, "temas_sifirlar")
                if P.contains(a, b) or P.contains(b, a):
                    self.relmodel.bump(ka, kb, "icinde")
                ar, ac = a.centroid; br, bc = b.centroid
                if abs(ar - br) < 1.5 or abs(ac - bc) < 1.5:
                    self.relmodel.bump(ka, kb, "hizali")
        # hareket eden nesne -> uzerinden gectigi duran nesne
        for c in changes:
            if c["effect"] == E_MOVE and c["after"] is not None:
                ka = cl(c["after"])
                acells = c["after"].cells
                for b in small:
                    kb = cl(b)
                    if kb == ka:
                        continue
                    if acells & b.cells:
                        self.relmodel.bump(ka, kb, "ust_gezer")
            if c["effect"] == E_MERGE:
                km = cl(c["after"]) if c["after"] is not None else -1
                for b in small:
                    kb = cl(b)
                    if kb != km:
                        self.relmodel.bump(km, kb, "temas_birlestirir")

    def do(self, kind, action, x, y):
        """Bir aksiyon uygula + beyin gozlesin."""
        before = self.hand.last["grid"]
        objs_before = P.find_objects(before)
        cl = lambda ob: self.mind.shapes.cluster_of(self.mind.shapes.token(ob))
        # TIKLANAN kume (ileri model icin): (x,y)'deki nesnenin kumesi
        tgt_cluster = -1
        if kind == "click":
            label = f"[A6@{x},{y}]"
            self.last_click = (int(x), int(y))
            for ob in objs_before:
                if (y, x) in ob.cells:
                    tgt_cluster = cl(ob); break
            obs = self.hand.click(x, y)
            touched = self._touched(before, x, y)
        else:
            label = f"[A{action}]"
            obs = self.hand.act(action)
            touched = None
        after = obs["grid"]
        present = {}
        for ob in objs_before:
            k = cl(ob)
            present[k] = present.get(k, 0) + ob.size
        # GIZLI FAZ (aksiyon ONCESI): aktif secim/firsat latenti -> ileri-model anahtari
        hidden_before = self.hidden_phase()
        res = self.mind.observe(action, label, before, after)
        # ILERI MODEL: (aksiyon, tiklanan-kume, GIZLI-FAZ) -> uretilen olaylar
        self.mind.record_model(action, tgt_cluster,
                               [t for t, _ in res.get("uretilen", [])], hidden_before)
        # NONDETERMINIZM: ayni (grid,aksiyon,kume) farkli sonuc -> GIZLI DURUM VAR kaniti
        tkey = (self._fp(before), action, tgt_cluster)
        outs = self._trans.setdefault(tkey, set())
        afp = self._fp(after)
        if outs and afp not in outs:
            self.has_hidden = True
        outs.add(afp)
        leveled_now = obs["levels_completed"] > self.prev_level
        cev, moved_pairs = [], []
        for c in res["changes"]:
            cb = cl(c["before"]) if c["before"] is not None else -1
            ca = cl(c["after"]) if c["after"] is not None else -1
            cev.append((cb, ca, c["effect"]))
        # LATENT guncelle: DOGAN kucuk nesne = "secildi/firsat" (+), KAYBOLAN/BIRLESEN = tuketildi (-)
        from transition import E_APPEAR, E_VANISH, E_MERGE
        for c in res["changes"]:
            if c["effect"] == E_APPEAR and c["after"] is not None and c["after"].size <= 40:
                self.pending.add(cl(c["after"]))
            elif c["effect"] in (E_VANISH, E_MERGE):
                kk = cl(c["before"]) if c["before"] is not None else (cl(c["after"]) if c["after"] is not None else -1)
                self.pending.discard(kk)
        self.rolemodel.update(action, cev, present, self.grid_area, leveled_now)
        self.dynmodel.observe(present)
        # ODUL: degisim/birlesme/kazanma +, duraganlik -
        went_back = (self._fp(after) == self.start_fp and self._fp(before) != self.start_fp)
        # BELIRSIZ ILISKI gozlemi (davranistan): uzerinde-gezer/temas-sifirlar/birlesir...
        self._observe_relations(objs_before, res["changes"], went_back, cl)
        r, why = self.reward.score(self.mind.step, action, res["changes"],
                                   leveled_now, went_back, res["yeni_tokenlar"],
                                   obs["levels_completed"], res.get("uretilen", []))
        # --- ILERLEME OLCUTU: HEDEF HIPOTEZINE yaklasma (insan gibi) ---
        # oyun durumu -> kume adetleri + renk/nesne sayisi
        objs_after = P.find_objects(after)
        counts = {}
        colors = set()
        for ob in objs_after:
            if ob.size > 200:            # dev arka plan/tahta haric
                continue
            counts[cl(ob)] = counts.get(cl(ob), 0) + 1
            colors.add(ob.color)
        nobj = sum(counts.values())
        # hedef hipotezi yoksa sec
        if self.goal.hyp is None:
            self.goal.pick(counts)
            self.path_best = None
        # bu hipoteze gore olcum (dusuk = hedefe yakin)
        m = self.goal.measure(self.goal.hyp, counts, len(colors), nobj)
        if self.path_best is None:
            self.path_best = m
        # ILERLEME = hedefe DAHA YAKIN olduk (olcum dustu)
        progress = m < self.path_best
        if progress:
            self.path_best = m
        # --- GERI-IZLEMELI ARAMA yol/duvar takibi ---
        mt = getattr(self, "_move_type", "fresh")
        if mt == "replay":
            self.path.append((kind, action, x, y))   # prefix'i yeniden kur
        elif mt == "fresh":
            self.tried.setdefault(self._cur_depth, set()).add(self._cur_key)
            self.path.append(self._cur_move)
            wall = (obs["state"] == "GAME_OVER") or went_back or not progress
            if leveled_now:
                # SEVIYE ATLADI: hipotez DOGRULANDI. Ogrenilenler KALIR (hedef, ileri-model,
                # olay-degerleri) -> yeni seviyede ESKI BILGIYI kullanir. Sadece ARAMA YOLU sifir.
                self.stuck = 0
                self.goal.confidence += 1
                self.path = []; self.tried = {}; self.replay = []
                self.path_best = None
                self.start_fp = self._fp(after)   # yeni seviye baslangici
            elif wall:
                self._deadend = True
                self.stuck += 1
                # cok takildik -> HIPOTEZI CURUT + rastgele kesif (insan gibi)
                if self.stuck >= 8:
                    self.goal.falsify()           # bu hedef yanlismis -> degistir
                    self.random_burst = 3         # birkac rastgele hamle
                    self.stuck = 0
            else:
                self.stuck = 0
        # aksiyon-degeri (odul-gudumlu kesif icin ortalama)
        av = self.act_value.setdefault(action, [0.0, 0])
        av[0] += r; av[1] += 1
        self.plan.push(res["yeni_tokenlar"])
        if leveled_now:
            self.plan.on_win()
        self.last_reward = {"r": r, "why": why, "total": round(self.reward.total, 1)}
        # ust-duzey: seviye gecildi / WIN -> token
        if obs["levels_completed"] > self.prev_level or obs["state"] == "WIN":
            gt, gyeni = self.mind.record_goal(action, label)
            if gyeni:
                res["yeni_tokenlar"].append(gt)
            self.clicked_shapes = set()      # yeni seviye: merak sifirla
        self.prev_level = obs["levels_completed"]
        # HAFIZA + GERI ALGILAMA: bu aksiyon bizi BASA/onceki bir duruma dondurdu mu?
        before_fp = self._fp(before)
        new_fp = self._fp(after)
        if new_fp == self.start_fp and before_fp != self.start_fp:
            bt, byeni = self.mind.record_backward(action, label)   # A0 = geri
            if byeni:
                res["yeni_tokenlar"].append(bt)
            self.back_actions.add(action)      # bu aksiyon geri goturuyor -> kacin
        self.visited.add(new_fp)
        # PLANLAYICI: bu adimda BELIREN nesneler (hedef adaylari)
        self.last_appeared = self._appeared(before, after)
        # ROL ogren: birlesme olan renk = KARGO
        from transition import E_MERGE
        for c in res["changes"]:
            if c["effect"] == E_MERGE:
                self.roles[c["color"]] = "kargo"
        # MERAK: bir tik YENI olay uretmediyse o konumu "sikici" isaretle (tekrarlama)
        if kind == "click" and not res["yeni_tokenlar"]:
            self.boring.add((int(x) // 5, int(y) // 5))
        if action == 0:
            self.clicked_shapes = set(); self.boring = set()  # reset: taze kesif
            self.plan.on_reset()
            self.pending = set()          # gizli faz sifir (yeni oyun/temiz baslangic)
            if getattr(self, "_move_type", "") == "reset":
                self.path = []            # backtrack reset: prefix replay ile yeniden kurulacak
        # el kaydi
        known = describe(action)
        yeni_desc = [f"#{t} {self.mind.events.info[t]['desc']}" for t in res["yeni_tokenlar"]]
        self.last_hand = {
            "desc": f"{label}  ({known.split('—')[0].strip() if '—' in known else known[:40]})",
            "touched": touched, "action": action,
            "yeni": yeni_desc, "olu": res["olu"],
        }
        return res

    def _touched(self, grid, x, y):
        """Tiklanan (x,y) hangi nesneye denk geldi?"""
        objs = P.find_objects(grid)
        for o in objs:
            if (y, x) in o.cells:
                return f"renk{o.color} nesne ({o.size} hucre)"
        # en yakin
        best, bo = None, None
        for o in objs:
            cy, cx = o.centroid
            d = abs(cy - y) + abs(cx - x)
            if best is None or d < best:
                best, bo = d, o
        return (f"bos alan (en yakin: renk{bo.color})" if bo else "bos alan")

    def snapshot(self):
        o = self.hand.last
        return {
            "game": self.game,
            "grid": o["grid"],
            "state": o["state"],
            "level": o["levels_completed"],
            "win_levels": o["win_levels"],
            "available": o["available"],
            "n_frames": o["n_frames"],
            "eye": self.mind.eye_tokens(o["grid"]),
            "hand": self.last_hand,
            "brain": self.mind.event_table(),
            "roles": self.rolemodel.table(self.grid_area),
            "reward": getattr(self, "last_reward", {"r": 0, "why": "-", "total": 0}),
            "values": self.reward.value_table()[:8],
            "action_meanings": self.mind.action_meanings(),
            "shape_actions": self.mind.shape_actions(),
            "relations": self.relmodel.table()[:10],
            "hidden": {"var": self.has_hidden, "pending": len(self.pending)},
            "dynamics": [d for d in self.dynmodel.table() if d["oruntu"] != "duragan/karma"][:8],
            "routes": len(self.plan.routes),
            "search": {"derinlik": len(self.path), "replay": len(self.replay),
                       "mod": getattr(self, "_move_type", "-"),
                       "hedef": str(self.goal.hyp), "guven": round(self.goal.confidence, 0),
                       "path_best": self.path_best, "rastgele": self.random_burst},
            "adim": self.mind.step,
        }


SES = Session("lf52")

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Ajan Gozlem</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#0d0f14;color:#e6e6e6;font:13px system-ui,sans-serif;height:100vh;
 display:grid;grid-template-columns:270px 1fr 340px;grid-template-rows:auto 1fr auto;
 grid-template-areas:"top top top" "eye game brain" "hand hand hand";overflow:hidden}
#top{grid-area:top;display:flex;gap:12px;align-items:center;padding:8px 12px;background:#151822;border-bottom:1px solid #262b38;flex-wrap:wrap}
#eye{grid-area:eye;border-right:1px solid #262b38;padding:10px;overflow:auto}
#game{grid-area:game;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:12px;overflow:auto}
#brain{grid-area:brain;border-left:1px solid #262b38;padding:10px;overflow:auto}
#hand{grid-area:hand;border-top:1px solid #262b38;padding:8px 12px;background:#0a0c11;min-height:70px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#7a9;margin:0 0 8px}
.badge{padding:3px 8px;border-radius:6px;background:#1b1f2b;border:1px solid #2a3040;font-size:12px}
.win{background:#14361c;border-color:#2f7d3f;color:#7CFC9E}.over{background:#3a1414;border-color:#7d2f2f;color:#ff8a8a}
#board{display:grid;background:#000;border:2px solid #333}
.cell{width:12px;height:12px;display:flex;align-items:center;justify-content:center;font:8px/1 monospace;font-weight:700}
select,button{background:#1b1f2b;color:#cfe;border:1px solid #3a4256;border-radius:6px;padding:5px 9px;font-size:13px;cursor:pointer}
button:hover{background:#2a3350}
.spacebtn{background:#1b2540;font-weight:700;padding:6px 16px}
.row{display:flex;gap:6px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;font-size:12px}
td{padding:3px 5px;border-bottom:1px solid #1c2130;vertical-align:top}
.cnt{color:#7CFC9E;font-weight:700;text-align:right;width:30px}
.new{background:#14361c}
.grp{display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid #171b26}
.sw{width:14px;height:14px;border-radius:3px;border:1px solid #333}
.muted{color:#6b7688}
kbd{background:#222a3a;border:1px solid #3a4460;border-radius:4px;padding:1px 6px;font-size:11px}
#nums button{min-width:34px}
</style></head><body>
<div id="top">
 <select id="gamesel"></select>
 <span id="hud"></span>
 <span style="flex:1"></span>
 <span class="badge">Adım: <b id="adim">0</b></span>
 <span class="badge" id="rewbadge">ödül: 0</span>
 <span class="badge" id="searchbadge">arama</span>
 <button class="spacebtn" onclick="step()">SPACE ▶ ajan adım</button>
 <button onclick="wipe()">beyni sıfırla</button>
 <button onclick="reset()">oyunu resetle</button>
</div>

<div id="eye"><h2>👁 GÖZ — şekil sözlüğü (sıklık)</h2><div id="eyebody"></div>
  <h2 style="margin-top:12px">🧩 BİLEŞİK ŞEKİLLER (katman 2)</h2><div id="compbody" class="muted">-</div>
</div>

<div id="game">
 <div id="board"></div>
 <div class="row" id="nums"></div>
 <div class="muted"><kbd>SPACE</kbd> = ajan sıradaki adımı · grid'e tık / rakam = sen sür</div>
</div>

<div id="brain">
  <h2>🎯 ROL (davranıştan, isimsiz)</h2><div id="rolebody" class="muted">-</div>
  <h2 style="margin-top:12px">🔗 İLİŞKİ</h2><div id="relbody" class="muted">-</div>
  <h2 style="margin-top:12px">🔄 DİNAMİK</h2><div id="dynbody" class="muted">-</div>
  <h2 style="margin-top:12px">🧠 OLAY-TOKEN</h2><div id="brainbody"><span class="muted">henüz yok</span></div>
</div>

<div id="hand">
  <div style="display:flex;gap:20px;flex-wrap:wrap">
    <div style="flex:1;min-width:200px"><h2>✋ EL — son ne yaptı</h2><div id="handbody"></div></div>
    <div style="flex:2;min-width:300px"><h2>🕹 AKSİYON ANLAMLARI (A1-A7 ne yapar — öğrenilen)</h2><div id="actmean" class="muted">-</div></div>
    <div style="flex:2;min-width:300px"><h2>🎬 ŞEKLE-TIKLAMA (hangi şekle tık ne yapar)</h2><div id="shpact" class="muted">-</div></div>
  </div>
</div>

<script>
const COLORS=%COLORS%;
async function api(p,b){const r=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});return r.json();}
async function get(){const r=await fetch('/api/state');return r.json();}

function render(s){
 document.getElementById('adim').textContent=s.adim;
 const hud=document.getElementById('hud');
 let cls=s.state==='WIN'?'badge win':(s.state==='GAME_OVER'?'badge over':'badge');
 hud.innerHTML=`<span class="${cls}">${s.state}</span> <span class="badge">Seviye ${s.level}/${s.win_levels??'?'}</span> <span class="badge">gecerli [${s.available.join(',')}]</span>`;
 // grid
 const g=s.grid,n=g.length,b=document.getElementById('board');
 b.style.gridTemplateColumns=`repeat(${n},12px)`;b.innerHTML='';
 for(let y=0;y<n;y++)for(let x=0;x<g[y].length;x++){const v=g[y][x];const c=document.createElement('div');c.className='cell';c.style.background=COLORS[v]||'#f0f';c.textContent=v;c.style.color=lum(COLORS[v])>0.55?'rgba(0,0,0,.7)':'rgba(255,255,255,.8)';c.onclick=()=>act(6,x,y);b.appendChild(c);}
 // eye — her sekil bir TOKEN (sayi) + gorsel numune
 const e=s.eye;const eb=document.getElementById('eyebody');
 const rolMap={},rolVec={};(s.roles||[]).forEach(r=>{rolMap[r.kume]=r.rol;rolVec[r.kume]=r.vec;});
 // ROL renkleri numaradan uretilir (isim YOK, sadece R0,R1,...)
 const rolPalet=['#FFDC00','#88D8F1','#4FCC30','#F93C31','#A356D6','#FF851B','#1E93FF','#E53AA3','#6b7688','#7CFC9E'];
 eb.innerHTML=`<div class="badge">arka plan ${e.bg} · ${e.n} nesne · ${e.kume_sayisi} şekil-token (tümü)</div>`;
 e.sekiller.forEach(sk=>{
   const row=document.createElement('div');row.className='grp';
   if(sk.ekranda>0){row.style.background='#12251a';}   // su an ekranda olan vurgulu
   const cv=document.createElement('canvas');drawShape(cv,sk.mask,sk.h,sk.w,COLORS[sk.renkler[0]]);
   const txt=document.createElement('div');txt.style.fontSize='11px';
   const rol=rolMap[sk.token];
   const rolet=(rol!=null)?` <span title="${(rolVec[sk.token]||[]).join(',')}" style="background:${rolPalet[rol%rolPalet.length]};color:#000;padding:1px 6px;border-radius:4px;font-weight:700">R${rol}</span>`:'';
   const ekr=sk.ekranda>0?` <span style="color:#4FCC30">●ekranda×${sk.ekranda}</span>`:` <span class="muted">○</span>`;
   txt.innerHTML=`<b style="color:#7CFC9E">K${sk.token}</b>${rolet} · <b style="color:#FFDC00">${sk.siklik}× görüldü</b>${ekr}`
     +`<br><span class="muted">${sk.h}×${sk.w} · ${sk.boyut}px · renk ${sk.renkler.join(',')} · ${sk.ornek_sayisi} tk</span>`;
   row.appendChild(cv);row.appendChild(txt);eb.appendChild(row);
 });
 // BILESIK sekiller (katman 2)
 const cb=document.getElementById('compbody');
 if((e.bilesikler||[]).length){cb.innerHTML='';
   e.bilesikler.forEach(sk=>{
     const row=document.createElement('div');row.className='grp';
     if(sk.ekranda>0)row.style.background='#231f10';
     const cv=document.createElement('canvas');drawShape(cv,sk.mask,sk.h,sk.w,COLORS[sk.renkler[0]]||'#888');
     const txt=document.createElement('div');txt.style.fontSize='11px';
     const ekr=sk.ekranda>0?` <span style="color:#FFDC00">●ekranda${sk.uye?' '+sk.uye+'üye':''}</span>`:` <span class="muted">○</span>`;
     txt.innerHTML=`<b style="color:#FFDC00">C${sk.token}</b> · <b>${sk.siklik}× görüldü</b>${ekr}`
       +`<br><span class="muted">${sk.h}×${sk.w} · ${sk.boyut}px · renk ${sk.renkler.join(',')}</span>`;
     row.appendChild(cv);row.appendChild(txt);cb.appendChild(row);
   });
 }else cb.textContent='-';
 // hand
 const h=s.hand;let hh=`<div><b>${h.desc||'-'}</b></div>`;
 if(h.touched)hh+=`<div>değdiği: <b>${h.touched}</b></div>`;
 if(h.olu)hh+=`<div style="color:#ff8a8a">⚠ ETKİSİZ (ölü durum — reset gerekebilir)</div>`;
 if(h.yeni&&h.yeni.length)hh+=`<div style="color:#7CFC9E">yeni olay-token: ${h.yeni.join(' · ')}</div>`;
 document.getElementById('handbody').innerHTML=hh;
 // KATMAN-1: aksiyon anlamlari (A1-A7 ne yapar)
 const am=s.action_meanings||{};const amd=document.getElementById('actmean');
 let amh='';[1,2,3,4,5,7].forEach(a=>{const m=am[a];if(m&&m.length){amh+=`<div><b style="color:#4a9cff">A${a}</b> → ${m.map(x=>x.desc+' <span class="muted">('+x.sayi+')</span>').join(' , ')}</div>`;}});
 amd.innerHTML=amh||'<span class="muted">henüz denenmedi</span>';
 // KATMAN-2: sekle-tiklama
 const sa=s.shape_actions||{};const sad=document.getElementById('shpact');
 let sah='';Object.keys(sa).forEach(k=>{const m=sa[k];if(m&&m.length){sah+=`<div><b style="color:#A356D6">K${k}</b> tık → ${m.map(x=>x.desc+' <span class="muted">('+x.sayi+')</span>').join(' , ')}</div>`;}});
 sad.innerHTML=sah||'<span class="muted">henüz tıklama öğrenilmedi</span>';
 // odul badge
 const rw=s.reward||{};
 const rb=document.getElementById('rewbadge');
 rb.innerHTML=`ödül Σ${rw.total} <span style="color:${(rw.r||0)>=0?'#7CFC9E':'#ff8a8a'}">(${(rw.r||0)>=0?'+':''}${rw.r} ${rw.why||''})</span>`;
 const sr=s.search||{};const sb=document.getElementById('searchbadge');
 const modRenk={'fresh':'#4FCC30','replay':'#FFDC00','reset':'#ff8a8a'}[sr.mod]||'#8aa';
 const hd=(sr.hedef&&sr.hedef!=='None')?sr.hedef:'—';
 sb.innerHTML=`🎯 hedef-hipotezi <b style="color:#FFDC00">${hd}</b>${sr.rastgele?' <span style="color:#ff8a8a">🎲rastgele</span>':''} · 🔎 derinlik <b>${sr.derinlik||0}</b> · <span style="color:${modRenk}">${sr.mod||'-'}</span>`;
 // ROL — isimsiz R-numarasi + baskin davranis (rolPalet yukarida tanimli)
 const rd=document.getElementById('rolebody');
 if((s.roles||[]).length){let h='';(s.roles||[]).forEach(r=>{h+=`<span style="display:inline-block;margin:2px;padding:2px 7px;border-radius:5px;background:${rolPalet[r.rol%rolPalet.length]};color:#000;font-weight:700" title="${r.vec.join(',')}">K${r.kume}→R${r.rol}</span>`;});rd.innerHTML=h;}else rd.textContent='-';
 // ILISKI
 const reld=document.getElementById('relbody');
 if((s.relations||[]).length){let h='<table>';(s.relations||[]).forEach(x=>{const tags=[];if(x.ust_hareket)tags.push('üstünde-hareket×'+x.ust_hareket);if(x.deg>0.3)tags.push('değer');if(x.icinde>0.3)tags.push('içinde');if(x.hizali>0.3)tags.push('hizalı');h+=`<tr><td>K${x.a}↔K${x.b}</td><td class="muted">${tags.join(', ')||'-'}</td></tr>`;});h+='</table>';reld.innerHTML=h;}else reld.textContent='-';
 // DINAMIK
 const dyd=document.getElementById('dynbody');
 if((s.dynamics||[]).length){let h='';(s.dynamics||[]).forEach(d=>{h+=`<div>K${d.kume}: <b style="color:#FFDC00">${d.oruntu}</b></div>`;});dyd.innerHTML=h;}else dyd.textContent='-';
 // brain — olay tokenlari (sayisal) + OGRENILEN deger
 const t=s.brain;
 const vmap={};(s.values||[]).forEach(v=>vmap[v.token]=v.deger);
 if(!t.length){document.getElementById('brainbody').innerHTML='<span class="muted">henüz olay-token yok (0)</span>';}
 else{let bt='<table>';t.forEach(a=>{const dv=vmap[a.token];const val=(dv!=null&&dv!=0)?` <span style="color:#FFDC00" title="öğrenilen değer">◆${dv}</span>`:'';bt+=`<tr><td class="cnt">${a.sayi}×</td><td><b style="color:#7CFC9E">#${a.token}</b> ${a.desc}${val}<div class="muted">${a.aksiyon}</div></td></tr>`;});bt+='</table>';document.getElementById('brainbody').innerHTML=bt;}
 // num buttons
 const nb=document.getElementById('nums');nb.innerHTML='';
 [0,1,2,3,4,5,7].forEach(a=>{const btn=document.createElement('button');btn.textContent=a;if(s.available.includes(a)||a===0)btn.style.borderColor='#4a6cff';btn.onclick=()=>act(a);nb.appendChild(btn);});
}
function lum(hex){if(!hex)return 0;const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);return(0.299*r+0.587*g+0.114*b)/255;}
function drawShape(cv,mask,h,w,color){
 // buyuk sekilleri kucult: en fazla ~46px, hucre 1..10px
 const cell=Math.max(1,Math.min(10,Math.floor(46/Math.max(h,w||1))));
 cv.width=Math.max(1,w*cell);cv.height=Math.max(1,h*cell);
 cv.style.background='#0a0c11';cv.style.border='1px solid #222';cv.style.borderRadius='3px';cv.style.flex='0 0 auto';
 const ctx=cv.getContext('2d');ctx.fillStyle=color||'#f0f';
 (mask||[]).forEach(p=>ctx.fillRect(p[1]*cell,p[0]*cell,cell,cell));
}

async function step(){render(await api('/api/step'));}
async function act(a,x,y){render(await api('/api/act',{action:a,x:x,y:y}));}
async function reset(){render(await api('/api/reset'));}
async function wipe(){render(await api('/api/wipe'));}
async function selGame(g){render(await api('/api/game',{game:g}));}

document.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();step();}});
(async()=>{
 const sel=document.getElementById('gamesel');
 %GAMES%.forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;sel.appendChild(o);});
 sel.onchange=()=>selGame(sel.value);
 render(await get());
})();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            page = PAGE.replace("%COLORS%", json.dumps(COLOR_MAP)).replace("%GAMES%", json.dumps(GAMES))
            self._send(200, page, "text/html; charset=utf-8")
        elif p == "/api/state":
            with _LOCK: self._send(200, json.dumps(SES.snapshot()))
        else:
            self._send(404, b"{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        global SES
        with _LOCK:
            try:
                if self.path == "/api/step":
                    kind, a, x, y = SES.next_explore(); SES.do(kind, a, x, y)
                elif self.path == "/api/act":
                    a = int(body["action"])
                    if a == 6: SES.do("click", 6, int(body["x"]), int(body["y"]))
                    else: SES.do("press", a, None, None)
                elif self.path == "/api/reset":
                    SES.hand.reset(); SES.clicked_shapes = set()
                    SES.prev_level = SES.hand.last["levels_completed"]
                    SES.last_hand = {"desc": "RESET", "touched": None, "action": 0}
                elif self.path == "/api/wipe":
                    SES.mind = Mind(); SES.tried = set()
                elif self.path == "/api/game":
                    SES.start(body["game"])
                else:
                    self._send(404, b"{}"); return
                self._send(200, json.dumps(SES.snapshot()))
            except Exception as e:
                import traceback; traceback.print_exc()
                self._send(200, json.dumps({"error": str(e)}))


if __name__ == "__main__":
    port = int(os.environ.get("BRAIN_PORT", "8001"))
    print(f"Ajan gozlem -> http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
