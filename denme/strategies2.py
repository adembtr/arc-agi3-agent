#!/usr/bin/env python3
"""MAKRO (aksiyon-dizisi) yontemleri — asil eksik buydu (bkz REPORT.md).
Herkes '2 nesne kaldi'ya geliyor ama koordineli 2-adimli birlestirmeyi yapamiyor.

Hepsi GENEL (ezber YOK, ogrenme YOK): "tikla->yeni nesne belirdi->ona tikla" gibi
mekanizma kurallari. Oyun-bilgisi gomulu degil; birlesmeyi AJAN kesfeder.
"""
import random
from strategies import Base
from transition import E_MERGE, E_APPEAR, E_NOCHANGE, E_VANISH


def _appeared(before_objs, after_objs):
    """after'da olup before ile ortusmeyen KUCUK nesneler = BELIREN (firsat)."""
    out = []
    for a in after_objs:
        if a.size > 60:
            continue
        if not any(a.cells & b.cells for b in before_objs):
            cy, cx = a.centroid
            out.append((int(round(cx)), int(round(cy))))
    return out


# A) FIRSAT-ZINCIRI: tikla; yeni nesne belirirse HEMEN ona tikla (means-ends).
#    Birlestirmenin genel kesif kurali. Ezber degil.
class AffordanceChain(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.queue = []          # beklenen firsat tiklamalari (x,y)
        self.clicked = set()     # son turda tiklanan kume-konumlari (dongu kir)

    def choose(self, obs):
        # 1) belirmis firsat varsa ONA tikla (secim->hedef zinciri)
        if self.queue:
            x, y = self.queue.pop(0)
            return ("click", 6, -1, x, y)
        # 2) yoksa: bir kume temsilcisine tikla (firsat dogsun diye)
        c = [cd for cd in self.cands(obs) if cd[0] == "click"]
        if not c:
            c = self.cands(obs)
        if not c:
            return None
        # en az tiklanmis kumeyi sec (cesitlilik)
        c.sort(key=lambda cd: self._count(obs["fp"], cd) + self.rng.random() * 0.3)
        return c[0]

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        # BELIREN nesneleri firsat kuyruguna al
        app = _appeared(obs["objs"], obs2["objs"])
        for xy in app:
            self.queue.append(xy)


# B) TIK-CIFTI MAKRO: (kume Xi'ye tik, sonra kume Xj'ye tik) ciftlerini dene.
#    Arada baska aksiyon YOK (secim bozulmasin). Birlesme cifti boyle bulunur.
class ClickPairMacro(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.second = None       # ikinci tik (x,y) bekliyor
        self.tried_pairs = set()

    def choose(self, obs):
        if self.second is not None:
            xy = self.second; self.second = None
            return ("click", 6, -1, xy[0], xy[1])
        clicks = [cd for cd in self.cands(obs) if cd[0] == "click"]
        if len(clicks) < 1:
            return self.rng.choice(self.cands(obs)) if self.cands(obs) else None
        # denenmemis bir (A,B) cifti sec
        self.rng.shuffle(clicks)
        first = clicks[0]
        others = [cd for cd in clicks if cd[2] != first[2]] or clicks
        second = self.rng.choice(others)
        self.second = (second[3], second[4])
        return first


# C) GO-EXPLORE + FIRSAT-ZINCIRI: arsivle+don, oradan firsat-zinciriyle kesfet.
class GoExploreChain(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.archive = {}        # cell -> (traj, ziyaret)
        self.traj = []
        self.forced = []         # reset+replay kuyrugu
        self.queue = []          # firsat tiklamalari
        self.explore_left = 0

    @staticmethod
    def _cell(obs):
        # kaba hucre: (nesne sayisi, kume imzasi) — gurultu yerine anlamli durum
        sig = tuple(sorted((k, len(v)) for k, v in obs["clusters"].items()))
        return (obs["level"], sig)

    def choose(self, obs):
        if self.forced:
            return self.forced.pop(0)
        if self.queue:                       # firsat zinciri onceligi
            x, y = self.queue.pop(0)
            return ("click", 6, -1, x, y)
        c = [cd for cd in self.cands(obs) if cd[0] == "click"] or self.cands(obs)
        if not c:
            return None
        # butce bittiyse umut veren (az ziyaret) hucreye DON
        if self.explore_left <= 0 and self.archive:
            cell = min(self.archive, key=lambda f: self.archive[f][1])
            traj, v = self.archive[cell]
            self.archive[cell] = (traj, v + 1)
            self.forced = [("press", 0, -1, None, None)] + list(traj)
            self.traj = list(traj)
            self.explore_left = 10
            return self.forced.pop(0)
        self.explore_left -= 1
        cd = self.rng.choice(c)
        mv = ("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click" else ("press", cd[1], -1, None, None)
        self.traj.append(mv)
        return cd

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        # firsat zinciri
        for xy in _appeared(obs["objs"], obs2["objs"]):
            self.queue.append(xy)
        # arsivle (kaba hucre)
        cell = self._cell(obs2)
        if cell not in self.archive or len(self.traj) < len(self.archive[cell][0]):
            self.archive[cell] = (list(self.traj), self.archive.get(cell, (None, 0))[1])
        if cand is not None and cand[1] == 0:
            self.traj = []


# D) FIRSAT-ZINCIRI + YON: tik zinciriyle birlestir, sonra yon tuslariyla tasi.
#    (m0r0/lf52 gibi 'birlestir sonra tasi' oyunlari icin — yine genel.)
class ChainThenMove(AffordanceChain):
    def choose(self, obs):
        if self.queue:
            x, y = self.queue.pop(0)
            return ("click", 6, -1, x, y)
        # nesne az kaldiysa (birlestik) yon tuslariyla oyna (tasima)
        nobj = sum(len(v) for v in obs["clusters"].values())
        moves = [cd for cd in self.cands(obs) if cd[0] == "press" and cd[1] in (1, 2, 3, 4)]
        clicks = [cd for cd in self.cands(obs) if cd[0] == "click"]
        if nobj <= 4 and moves and self.rng.random() < 0.5:
            return self.rng.choice(moves)
        pool = clicks or self.cands(obs)
        if not pool:
            return None
        pool.sort(key=lambda cd: self._count(obs["fp"], cd) + self.rng.random() * 0.3)
        return pool[0]


# E) HEDEF-YAKINSAYAN GO-EXPLORE: hucre = nesne sayisi. min_obj'e goturen yolu
#    arsivle ve ORADAN devam et (nesne sayisini MONOTON azalt). Puzzle cozer gibi:
#    her turda "daha az nesne" durumuna ilerle, geri gitme.
class GoalConvergeGE(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.best_traj = []          # simdiye kadar EN AZ nesneye goturen yol
        self.best_nobj = 10 ** 9
        self.traj = []
        self.forced = []
        self.queue = []              # firsat tiklamalari (belirenler)
        self.since_improve = 0

    def choose(self, obs):
        if self.forced:
            return self.forced.pop(0)
        if self.queue:
            x, y = self.queue.pop(0)
            return ("click", 6, -1, x, y)
        c = [cd for cd in self.cands(obs) if cd[0] == "click"] or self.cands(obs)
        if not c:
            return None
        # uzun suredir ilerleme yok -> EN IYI duruma reset+replay ile don, oradan dene
        if self.since_improve >= 12 and self.best_traj:
            self.forced = [("press", 0, -1, None, None)] + list(self.best_traj)
            self.traj = list(self.best_traj)
            self.since_improve = 0
            return self.forced.pop(0)
        cd = self.rng.choice(c)
        mv = ("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click" else ("press", cd[1], -1, None, None)
        self.traj.append(mv)
        return cd

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        for xy in _appeared(obs["objs"], obs2["objs"]):
            self.queue.append(xy)
        if cand is not None and cand[1] == 0:
            self.traj = []
        nobj = sum(len(v) for v in obs2["clusters"].values())
        if nobj < self.best_nobj:            # DAHA AZ nesne = ilerleme -> yolu sakla
            self.best_nobj = nobj
            self.best_traj = list(self.traj)
            self.since_improve = 0
        else:
            self.since_improve += 1


# F) E + YON: az nesne kalinca yon tuslariyla da tasima dene (birlestir+tasi oyunlari)
class GoalConvergeMove(GoalConvergeGE):
    def choose(self, obs):
        if self.forced:
            return self.forced.pop(0)
        if self.queue:
            x, y = self.queue.pop(0)
            return ("click", 6, -1, x, y)
        nobj = sum(len(v) for v in obs["clusters"].values())
        if self.since_improve >= 12 and self.best_traj:
            self.forced = [("press", 0, -1, None, None)] + list(self.best_traj)
            self.traj = list(self.best_traj); self.since_improve = 0
            return self.forced.pop(0)
        moves = [cd for cd in self.cands(obs) if cd[0] == "press" and cd[1] in (1, 2, 3, 4)]
        clicks = [cd for cd in self.cands(obs) if cd[0] == "click"]
        # az nesne kaldiysa yar1 yon-tusu (tasima) yar1 tik
        if nobj <= 6 and moves and self.rng.random() < 0.45:
            cd = self.rng.choice(moves)
        else:
            cd = self.rng.choice(clicks or self.cands(obs))
        mv = ("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click" else ("press", cd[1], -1, None, None)
        self.traj.append(mv)
        return cd


# G) YENI-DURUM GO-EXPLORE: hucre = TAM grid-fp. Sadece HIC GORULMEMIS durum
#    ureten hamleleri odulle; gorulmus duruma goturen (toggle/geri) hamleyi cezalandir.
#    Puzzle'da ilerleme = yeni durum acmak. Arsivden en YENI (az ziyaret) hucreden devam.
class NewStateGE(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.archive = {}            # fp -> (traj, ziyaret)
        self.traj = []
        self.forced = []
        self.queue = []
        self.since_new = 0

    def choose(self, obs):
        if self.forced:
            return self.forced.pop(0)
        if self.queue:
            x, y = self.queue.pop(0)
            return ("click", 6, -1, x, y)
        c = [cd for cd in self.cands(obs) if cd[0] == "click"] or self.cands(obs)
        if not c:
            return None
        # uzun sure yeni durum yoksa -> az ziyaret edilmis bir arsiv hucresinden devam
        if self.since_new >= 15 and len(self.archive) > 3:
            cell = min(self.archive, key=lambda f: self.archive[f][1])
            traj, v = self.archive[cell]
            self.archive[cell] = (traj, v + 1)
            self.forced = [("press", 0, -1, None, None)] + list(traj)
            self.traj = list(traj); self.since_new = 0
            return self.forced.pop(0)
        # bu durumda en az denenmis hamle (yeni durum acma sansi yuksek)
        c.sort(key=lambda cd: self._count(obs["fp"], cd) + self.rng.random() * 0.2)
        cd = c[0]
        mv = ("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click" else ("press", cd[1], -1, None, None)
        self.traj.append(mv)
        return cd

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        for xy in _appeared(obs["objs"], obs2["objs"]):
            self.queue.append(xy)
        if cand is not None and cand[1] == 0:
            self.traj = []
        fp = obs2["fp"]
        if fp not in self.archive:           # YENI durum acildi = ilerleme
            self.archive[fp] = (list(self.traj), 0)
            self.since_new = 0
        else:
            self.since_new += 1


# H) HIZLI-VAZGEC KURAL KESFI (kullanicinin tarifi):
#    - Bir CIFT dene: kume A'ya tikla -> bir sey acildiysa ona da tikla -> sonuc?
#    - Sonuc KALICI ILERLEME (yeni durum) ise -> bu kural DEGERLI, tekrar kullan.
#    - Ayni yaklasim 2 KEZ ise yaramazsa -> O KUMEYI/CIFTI KARA-LISTE, bir daha deneme.
#    Ezber YOK, ogrenme YOK. Sadece "ise yaramayani hemen birak" + firsat-zinciri.
class QuickGiveUp(Base):
    MAX_FAIL = 2                          # 2 kez ise yaramazsa vazgec

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fail = {}                   # kume -> pes pese basarisiz sayisi
        self.dead = set()                # vazgecilen kumeler
        self.queue = []                  # acilan firsat tiklamalari
        self.active = None               # su an denenen aday kimligi
        self.pre_fp = None
        self.seen_fp = set()             # gorulen durumlar (yeni durum = ilerleme)

    def choose(self, obs):
        # 1) bir sey acildiysa CIFTI tamamla: ona tikla (ama kuyruk sinirli — sonsuz
        #    zincire girip kesfi durdurma: en fazla 1 firsat tiki, sonra normal kesif)
        if self.queue:
            x, y = self.queue.pop(0)
            self.queue = []                 # kuyrugu bosalt (dongu/kilitlenme onle)
            return ("click", 6, -2, x, y)   # -2 = firsat tiki (ciftin 2. adimi)
        # 2) TUM aksiyon turleri: yon tuslari (1-4) + tik. Karalistede olmayan, az denenmis.
        #    Her aday icin kimlik = tik ise kume, tus ise ("A",n). Ise yaramayan hemen olur.
        pool = []
        for cd in self.cands(obs):
            ident = cd[2] if cd[0] == "click" else ("A", cd[1])
            if ident not in self.dead:
                pool.append((cd, ident))
        if not pool:
            self.dead.clear(); self.fail.clear()   # her sey karaliste -> temiz sayfa
            return ("press", 0, -1, None, None)
        pool.sort(key=lambda p: (self.fail.get(p[1], 0), self._count(obs["fp"], p[0])))
        cd, ident = pool[0]
        self.active = ident
        self.pre_fp = obs["fp"]
        return cd

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        # acilan firsatlari kuyruga al (ciftin 2. adimi olacak)
        app = _appeared(obs["objs"], obs2["objs"])
        for xy in app:
            self.queue.append(xy)
        # SONUC degerlendir (GENEL, birlesme YOK): kalici ilerleme = YENI durum acildi.
        #   Ise yaramadi = durum degismedi / gorulmus duruma dondu. 2 kez -> vazgec.
        if cand is None or cand[2] == -2:
            return                       # ciftin 2. adimi (firsat tiki) — ayri sayma
        k = self.active if self.active is not None else cand[2]
        new_state = obs2["fp"] not in self.seen_fp
        self.seen_fp.add(obs2["fp"])
        structural = any(c["effect"] != E_NOCHANGE for c in res["changes"])
        if new_state and structural:     # YENI durum acti -> degerli, sifirla
            self.fail[k] = 0
        else:                            # ayni yere dondu / etkisiz -> basarisiz
            self.fail[k] = self.fail.get(k, 0) + 1
            if self.fail[k] >= self.MAX_FAIL:
                self.dead.add(k)         # 2 KEZ ise yaramadi -> HEMEN VAZGEC


# I) YANLIS-ELEME AGIRLIGI + ODUL  (kullanicinin fikri)
#    W[baglam-token, aksiyon] = 1'den baslar; SADECE yanlista duser (carpimsal negatif).
#    YANLIS = etki-yok / gorulen duruma geri-donus / game-over. (hedefi bilmeden gorulur)
#    YANLIS DEGIL = herhangi bir yapisal degisim (cok-adimli dogru hamleyi korur).
#    ODUL = yeni durum acmak (+), seviye atlamak (++). Baglam TOKEN -> genellesir.
#    Go-Explore omurga: umut veren duruma reset+replay ile don. Tum aksiyonlar denenir.
class WrongElimReward(Base):
    BETA = 0.15          # yanlista W carpani (hizli kapat)
    LAMBDA = 1.0         # kesif(yeni durum) agirligi

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.W = {}                  # (ctx_token, act_id) -> agirlik [0..1], init 1
        self.seen_fp = set()
        self.value = {}              # (ctx,act) -> ogrenilen odul (kredi)
        self.archive = {}            # fp -> (traj, ziyaret)
        self.traj = []
        self.forced = []
        self.queue = []              # firsat tiklamalari (belirenler)
        self.since_new = 0

    def _ident(self, cd):
        # ZENGIN baglam: (aksiyon, sekil-token). tik=(6,K) ayri, tus=(n,-1) ayri.
        # Boylece hem TIK hem TUS hem OLAY(farkli aksiyon) ayri ayri elenir.
        # Yeni sekil -> yeni token -> yeni ident -> W=1 (TAZE, elenmez).
        if cd[0] == "click":
            return (6, cd[2])
        return (cd[1], -1)

    def _w(self, ident):
        return self.W.get(ident, 1.0)

    def _v(self, ident):
        return self.value.get(ident, 0.0)

    def choose(self, obs):
        if self.forced:
            return self.forced.pop(0)
        if self.queue:               # acilan firsati HEMEN dene (secim->hedef zinciri)
            x, y = self.queue.pop(0); self.queue = []
            return ("click", 6, -2, x, y)
        c = self.cands(obs)
        if not c:
            return None
        # uzun sure yeni durum yok -> umut veren (az ziyaret) arsiv hucresine DON
        if self.since_new >= 15 and len(self.archive) > 3:
            cell = min(self.archive, key=lambda f: self.archive[f][1])
            traj, v = self.archive[cell]; self.archive[cell] = (traj, v + 1)
            self.forced = [("press", 0, -1, None, None)] + list(traj)
            self.traj = list(traj); self.since_new = 0
            return self.forced.pop(0)
        # PUAN = W(canli mi) * (odul + λ*yenilik_bonusu)
        def score(cd):
            ident = self._ident(cd)
            w = self._w(ident)
            if w < 0.05:                       # elenmis -> neredeyse asla
                return -1.0 + self.rng.random() * 0.01
            novelty = 1.0 / (self._count(obs["fp"], cd) + 1)
            return w * (self._v(ident) + self.LAMBDA * novelty) + self.rng.random() * 0.05
        cd = max(c, key=score)
        mv = ("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click" else ("press", cd[1], -1, None, None)
        self.traj.append(mv)
        return cd

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        # firsat zinciri: belirenler
        for xy in _appeared(obs["objs"], obs2["objs"]):
            self.queue.append(xy)
        if cand is None:
            return
        if cand[1] == 0:
            self.traj = []
            return
        ident = self._ident(cand)
        structural = any(c["effect"] != E_NOCHANGE for c in res["changes"])
        reverted = obs2["fp"] in self.seen_fp
        new_state = obs2["fp"] not in self.seen_fp
        game_over = (obs2["state"] == "GAME_OVER")
        leveled = obs2["level"] > obs["level"]
        self.seen_fp.add(obs2["fp"])

        # --- YANLIS-ELEME (W sadece duser) ---
        if (not structural) or game_over:
            # ETKI YOK ya da GAME_OVER = kesin yanlis -> agirligi kir
            self.W[ident] = self._w(ident) * self.BETA
        elif reverted:
            # gorulen duruma geri dondu = kismen yanlis (dongu) -> hafif kir
            self.W[ident] = self._w(ident) * 0.6
        # structural + yeni durum -> W'ye DOKUNMA (canli kalir)

        # --- ODUL (kredi) ---
        if leveled:
            self.value[ident] = self._v(ident) + 10.0     # seviye = buyuk odul
            self.since_new = 0
            # SEVIYE ATLADI: oyun fazi degisti -> elenen aksiyonlara IKINCI SANS (revive).
            #   Yeni sekiller zaten taze (yeni token). Eski elemeler yumusatilir.
            for i in list(self.W):
                self.W[i] = min(1.0, self.W[i] * 4.0)
            self.seen_fp = set()                          # yeni bolum: durum hafizasi tazele
        elif new_state and structural:
            self.value[ident] = self._v(ident) + 0.3       # yeni durum acmak = kucuk odul
            self.since_new = 0
        else:
            self.since_new += 1

        # --- Go-Explore arsiv ---
        fp = obs2["fp"]
        if fp not in self.archive or len(self.traj) < len(self.archive[fp][0]):
            self.archive[fp] = (list(self.traj), self.archive.get(fp, (None, 0))[1])


MACROS = {
    "A_afford_chain": AffordanceChain,
    "B_click_pair": ClickPairMacro,
    "C_goexplore_chain": GoExploreChain,
    "D_chain_then_move": ChainThenMove,
    "E_goal_converge": GoalConvergeGE,
    "F_goal_converge_move": GoalConvergeMove,
    "G_new_state": NewStateGE,
    "H_quick_giveup": QuickGiveUp,
    "I_wrong_elim_reward": WrongElimReward,
}
