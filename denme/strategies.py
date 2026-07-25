#!/usr/bin/env python3
"""13 KESIF/KARAR yontemi — hepsi saf matematik/olasilik/fizik.
LLM YOK, insan-izi YOK, onceden-egitilmis model YOK. Hepsi oyunda sifirdan.

Ortak arayuz:
  __init__(env, mind, seed)
  choose(obs) -> aday (kind,a,kume,x,y) | None
  update(obs, cand, obs2, res)
"""
import math
import random
from transition import E_MERGE, E_NOCHANGE


def _key(cand):
    return (cand[1], cand[2])            # (aksiyon, kume)


class Base:
    def __init__(self, env, mind, seed=0):
        self.env = env
        self.mind = mind
        self.rng = random.Random(seed)
        self.N = {}                      # (fp,a,k) -> deneme sayisi
        self.prev_measure = None

    def cands(self, obs):
        return self.env.candidates(obs)

    def _count(self, fp, cand):
        return self.N.get((fp, _key(cand)[0], _key(cand)[1]), 0)

    def update(self, obs, cand, obs2, res):
        if cand is not None:
            k = (obs["fp"], cand[1], cand[2])
            self.N[k] = self.N.get(k, 0) + 1

    def choose(self, obs):
        raise NotImplementedError


# 1) RASTGELE (temel cizgi)
class Random(Base):
    def choose(self, obs):
        c = self.cands(obs)
        return self.rng.choice(c) if c else None


# 2) SAYIM-TABANLI UCB (kesif bonusu = 1/sqrt(N))
class CountUCB(Base):
    C = 1.4

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        def val(cd):
            n = self._count(obs["fp"], cd)
            return self.C / math.sqrt(n + 1)      # az denenmis -> yuksek
        return max(c, key=val)


# 3) YENILIK (gorulmemis durum-aksiyonu tercih et)
class Novelty(Base):
    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        untried = [cd for cd in c if self._count(obs["fp"], cd) == 0]
        return self.rng.choice(untried) if untried else self.rng.choice(c)


# 4) BEKLENEN SERBEST ENERJI (exploit + λ·epistemic)  [active inference]
class EFE(Base):
    LAMBDA = 0.7

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        hph = 0
        vfn = lambda t: 0.0               # deger yok (kazanma yok) -> saf epistemic
        def val(cd):
            ex, ep = self.mind.efe(cd[1], cd[2], hph, vfn)
            return ex + self.LAMBDA * ep
        return max(c, key=val)


# 5) MERAK — ileri-model belirsizligi yuksek olani sec (tahmin entropisi)
class Curiosity(Base):
    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        def unc(cd):
            pred = self.mind.predict(cd[1], cd[2], 0)
            if not pred:
                return 10.0               # hic bilmiyoruz -> en belirsiz
            H = -sum(p * math.log(p + 1e-9) for _, p in pred)
            return H
        return max(c, key=unc)


# 6) MAKS-ENTROPI durum ziyareti (en az gorulen durum-kovasi)
class MaxEntropy(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.state_visits = {}

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        # en az denenmis (fp,cand) — durum ziyaret entropisini artirir
        return min(c, key=lambda cd: self._count(obs["fp"], cd))

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        self.state_visits[obs2["fp"]] = self.state_visits.get(obs2["fp"], 0) + 1


# 7) EMPOWERMENT — gecmiste EN COK FARKLI sonuc ureten (kume,aksiyon) = kontrol
class Empowerment(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.outcomes = {}                # (a,k) -> set(sonuc_fp)

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        def emp(cd):
            s = self.outcomes.get(_key(cd), set())
            return len(s) + self.rng.random()  # cok farkli sonuc -> yuksek kontrol
        return max(c, key=emp)

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        if cand is not None:
            self.outcomes.setdefault(_key(cand), set()).add(obs2["fp"])


# 8) THOMPSON ORNEKLEME (Dirichlet posteriordan cek, argmax)
class Thompson(Base):
    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        def sample(cd):
            n = self._count(obs["fp"], cd)
            # az denenmise Beta(1, N) benzeri optimist ornek
            return self.rng.betavariate(1, n + 1)
        return max(c, key=sample)


# 9) HEDEF-GUDUMLU acgozlu (nesne sayisini azalt = birlestirme sezgisi)
class GoalGreedy(Base):
    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        # ileri-modelde birlesme/azaltma ureten aday -> tercih; yoksa yenilik
        def val(cd):
            pred = self.mind.predict(cd[1], cd[2], 0)
            merge_p = 0.0
            for t, p in pred:
                desc = self.mind.events.info.get(t, {}).get("desc", "")
                if "⊕" in desc or "−" in desc:
                    merge_p += p
            return merge_p * 5 + (1.0 / (self._count(obs["fp"], cd) + 1))
        return max(c, key=val)


# 10) NOVELTY SEARCH (davranis arsivi — olay-imzasindan uzak davranis ara)
class NoveltySearch(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.archive = []                 # olay-token frozenset'leri

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        # en az denenmis + arsive uzaklik (yaklasik: az denenmis)
        return min(c, key=lambda cd: self._count(obs["fp"], cd) + self.rng.random())

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        sig = frozenset(t for t, _ in res.get("uretilen", []))
        if sig and sig not in self.archive:
            self.archive.append(sig)


# 11) POMDP INANC BILGI-KAZANCI — nondeterminizm (gizli durum) cozen aksiyon
class BeliefInfoGain(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.trans = {}                   # (fp,a,k) -> set(sonuc_fp)

    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        # ciktisi en BELIRSIZ (ayni girdi farkli cikti) olani sec -> gizli durumu cozer
        def ig(cd):
            s = self.trans.get((obs["fp"], cd[1], cd[2]), set())
            return (2 if len(s) >= 2 else 0) + 1.0 / (len(s) + 1) + self.rng.random() * 0.1
        return max(c, key=ig)

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        if cand is not None:
            self.trans.setdefault((obs["fp"], cand[1], cand[2]), set()).add(obs2["fp"])


# 12) MODEL-TABANLI PLANLAMA (ogrenilen kume-gecis matrisinde ileri bakis)
class ModelPlan(Base):
    def choose(self, obs):
        c = self.cands(obs)
        if not c:
            return None
        # tek adim ileri: birlesme/azaltma olasiligi + belirsizlik
        def val(cd):
            ex, ep = self.mind.efe(cd[1], cd[2], 0, self._vfn)
            return ex + 0.5 * ep
        return max(c, key=val)

    def _vfn(self, t):
        desc = self.mind.events.info.get(t, {}).get("desc", "")
        if "⊕" in desc:                   # birlesme = degerli varsay
            return 3.0
        if "−" in desc or "▶" in desc:
            return 1.0
        return 0.0


# 13) GO-EXPLORE (arsiv + reset&replay ile umut veren duruma don, oradan kesfet)
#     Seyrek-odul icin en guclu klasik yontem. Bizim reset-only ortamla dogal uyum.
class GoExplore(Base):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.archive = {}                 # cell(fp) -> (traj, ziyaret)
        self.traj = []                    # su anki reset-sonrasi yol
        self.queue = []                   # zorunlu hamleler (reset + replay)
        self.explore_left = 0

    def choose(self, obs):
        if self.queue:
            return self.queue.pop(0)
        c = self.cands(obs)
        if not c:
            return None
        # kesif butcesi bittiyse: umut veren bir hucreye DON
        if self.explore_left <= 0 and self.archive:
            # en az ziyaret edilen hucreyi sec (kesif onceligi)
            cell = min(self.archive, key=lambda f: self.archive[f][1])
            traj, v = self.archive[cell]
            self.archive[cell] = (traj, v + 1)
            self.queue = [("press", 0, None, None)] + list(traj)
            self.traj = list(traj)
            self.explore_left = 8         # donunce 8 rastgele kesif
            return self.queue.pop(0)
        # rastgele kesfet + yolu kaydet
        self.explore_left -= 1
        cd = self.rng.choice(c)
        self.traj = self.traj + [("click", 6, cd[3], cd[4]) if cd[0] == "click"
                                 else ("press", cd[1], None, None)]
        return cd

    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        fp = obs2["fp"]
        # yeni/daha kisa yol -> arsive kaydet
        if fp not in self.archive or len(self.traj) < len(self.archive[fp][0]):
            self.archive[fp] = (list(self.traj), self.archive.get(fp, (None, 0))[1])
        if cand is not None and cand[0] == 0:
            self.traj = []


ALL = {
    "01_random": Random, "02_count_ucb": CountUCB, "03_novelty": Novelty,
    "04_efe": EFE, "05_curiosity": Curiosity, "06_max_entropy": MaxEntropy,
    "07_empowerment": Empowerment, "08_thompson": Thompson,
    "09_goal_greedy": GoalGreedy, "10_novelty_search": NoveltySearch,
    "11_belief_infogain": BeliefInfoGain, "12_model_plan": ModelPlan,
    "13_go_explore": GoExplore,
}
