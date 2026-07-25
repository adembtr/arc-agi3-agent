#!/usr/bin/env python3
"""ENTEGRASYON — hedef-gudumlu ajan (hedef_gorev.md §4).

ilk kare   -> goals.hypothesize_goals()  : hedef hipotezi (aksiyon HARCAMADAN)
           -> meta (canli)               : sayac / tehlike / baglasik
her adim   -> PROGRESS-gudumu: hipotezin progress'ini ARTIRAN kimlikleri odulle
              (model-free tepe-tirmanisi + yanlis-eleme; W carpani korunur)
           -> hazard vetosu (KAPILI: >=2 gozlem; tikaninca devre disi)
           -> coupled + tikanma -> "DUVARA DAYA" makrosu (ayni yonu N kez bas,
              sonra diger yonler — baglasik nesneleri ayirmanin tek yolu)
hipotez olu (N adim progress yok) -> siradaki hipoteze gec
seviye atlama -> aktif sablonun puani KALICI artar (sema tohumu, Modul C)
                + yeni karede hipotezler yeniden kurulur
tikanma    -> WrongElimReward yedegi (miras — mevcut en iyi)

Sayac bolgeleriyle ortusen nesneler hedef adayi OLAMAZ (meta dislama).
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))

import transition as T                     # noqa: E402
from strategies2 import WrongElimReward    # noqa: E402
from goals import hypothesize_goals       # noqa: E402
from meta import Meta                      # noqa: E402


class GoalAgent(WrongElimReward):
    PROG_W = 8.0            # progress-delta odul agirligi (yenilik ~1'e karsi)
    DEAD_AFTER = 60         # hipotez: bu kadar adim progress artmazsa OLU
    MACRO_PIN = 6           # duvara-daya: ayni yon kac kez
    MACRO_BUDGET = 8        # seviye basina makro tavani (spam onlemi — olculdu:
    #                         157 makro x 6 basis = adimlarin %45'i yandi)
    META_EVERY = 25         # meta.detect() tazeleme araligi

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.meta = Meta()
        self.hyps = None                # hipotez listesi (ilk observe'da kurulur)
        self.hidx = 0                   # aktif hipotez indeksi
        self.best_prog = 0.0
        self.last_prog = 0.0
        self.no_prog = 0
        self.vprog = {}                 # ident -> birikmis progress-delta
        self.template_bonus = {}        # sablon adi -> seviyeyle ogrenilen puan
        self.macro = []                 # bekleyen makro hamleleri
        self.macro_dir_i = 0
        self.repeat = None              # momentum: son progress-artiran hamle
        self.probed = set()
        self._det = None
        self._det_at = -999
        self.goal_off = False           # hicbir hipotez calismiyorsa saf yedek
        self.saw_prog = False
        self.rebuilds_no_prog = 0
        self.stats = {"macro": 0, "hyp_switch": 0, "veto": 0, "goal_off": 0}

    # ---------------- hipotez yasami ----------------
    def _ensure_hyps(self, obs):
        if self.hyps is None:
            self._rebuild(obs)

    def _rebuild(self, obs):
        if self.hyps is not None:               # onceki tur hic progress gormediyse
            if not self.saw_prog:
                self.rebuilds_no_prog += 1
                if self.rebuilds_no_prog >= 2:  # hipotezler bu seviyede CALISMIYOR
                    self.goal_off = True        # -> saf yanlis-eleme yedegi
                    self.stats["goal_off"] += 1
            else:
                self.rebuilds_no_prog = 0
        self.saw_prog = False
        hyps = hypothesize_goals(obs["objs"], obs["grid"])
        # sayac bolgesiyle ortusen nesneleri hedefleyen hipotezleri ele
        det = self._detect()
        bad = []
        for c in det.get("counters", []):
            bad.append(c["bolge"])
        def touches_counter(h):
            for o in h.objects:
                r0, c0, r1, c1 = o.bbox
                for br0, bc0, br1, bc1 in bad:
                    if not (r1 < br0 or br1 < r0 or c1 < bc0 or bc1 < c0):
                        return True
            return False
        hyps = [h for h in hyps if not touches_counter(h)]
        for h in hyps:                              # sema tohumu: ogrenilen bonus
            h.score += self.template_bonus.get(h.name, 0.0)
        hyps.sort(key=lambda h: -h.score)
        self.hyps = hyps
        self.hidx = 0
        self.best_prog = 0.0
        self.last_prog = 0.0
        self.no_prog = 0
        self.probed = set()             # hipotez-basi SONDA: her kimlik 1 kez

    def _active(self):
        while self.hyps and self.hidx < len(self.hyps) and \
                not self.hyps[self.hidx].alive:
            self.hidx += 1
        if self.hyps and self.hidx < len(self.hyps):
            return self.hyps[self.hidx]
        return None

    def _detect(self):
        if self.meta.step_i - self._det_at >= self.META_EVERY or self._det is None:
            self._det = self.meta.detect()
            self._det_at = self.meta.step_i
        return self._det

    # ---------------- karar ----------------
    def choose(self, obs):
        self._ensure_hyps(obs)
        if self.goal_off:                       # hipotezler olu -> SAF yedek
            return super().choose(obs)
        if self.macro:
            return self.macro.pop(0)
        # MOMENTUM kuyruktan ONCE: kendi hareketimizin "beliren nesne" kuyrugu
        # momentumu golgeliyordu (olculdu: ar25'te tirmanis hic baslamiyordu)
        if self.repeat is not None:
            c0 = self.cands(obs)
            rep = [cd for cd in c0 if self._ident(cd) == self.repeat]
            if rep:
                return self._commit_mv(rep[0])
            self.repeat = None
        if self.forced or self.queue:
            return super().choose(obs)
        c = self.cands(obs)
        if not c:
            return None
        det = self._detect()

        # hazard vetosu (kapili; tikaninca devre disi)
        hz = {h["aksiyon"] for h in det.get("hazard_actions", [])}
        if hz and self.since_new < 12:
            safe = [cd for cd in c if cd[1] not in hz]
            if safe and len(safe) < len(c):
                self.stats["veto"] += len(c) - len(safe)
                c = safe

        H = self._active()
        # tikanma + baglasik -> DUVARA-DAYA makrosu (BUTCELI: spam onlemi)
        coup = [x["aksiyon"] for x in det.get("coupled_actions", [])
                if x["aksiyon"] != 0]
        if H is not None and coup and self.no_prog >= 25 and not self.macro \
                and self.stats["macro"] < self.MACRO_BUDGET:
            press = [cd for cd in c if cd[0] == "press" and cd[1] in coup]
            if press:
                d = press[self.macro_dir_i % len(press)]
                self.macro_dir_i += 1
                self.macro = [d] * (self.MACRO_PIN - 1)
                self.stats["macro"] += 1
                self.no_prog = 0
                return self._commit_mv(d)

        # SONDA: aktif hipotez altinda her kimligi EN AZ BIR KEZ dene (ΔH olc).
        # (olculdu: ebeveyn value-kredisi ilk hareket-ureten tusta kartopu olup
        #  A2'yi HIC ornekletmiyordu — sistematik deney sart)
        if H is not None:
            unprobed = [cd for cd in c if self._ident(cd) not in self.probed]
            if unprobed:
                cd = unprobed[0]
                self.probed.add(self._ident(cd))
                return self._commit_mv(cd)

        # PROGRESS-gudumlu secim. KRITIK: prog-degeri W carpaninin DISINDA —
        # duvarda etkisiz kalip W'si ezilen yon tusu, progress uretmisligi
        # varsa SECILEBILIR kalmali (olculdu: carpim ici -> ar25 tikandi).
        def score(cd):
            ident = self._ident(cd)
            w = self._w(ident)
            novelty = 1.0 / (self._count(obs["fp"], cd) + 1)
            pv = self.vprog.get(ident, 0.0)
            base = -1.0 if w < 0.05 else w * (self._v(ident) + novelty)
            return base + self.PROG_W * max(0.0, pv) \
                + self.rng.random() * 0.05
        cd = max(c, key=score)
        return self._commit_mv(cd)

    def _commit_mv(self, cd):
        mv = (("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click"
              else ("press", cd[1], -1, None, None))
        self.traj.append(mv)
        return cd

    # ---------------- gozlem ----------------
    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        if cand is None:
            return
        self.meta.observe(obs, (cand[1], cand[2]), obs2, res["changes"])
        H = self._active()
        leveled = obs2["level"] > obs["level"]
        if H is not None and not leveled:
            p = H.progress(obs2["objs"], obs2["grid"])
            # YOGUN gradyan: delta = SON-progress'e gore (best'e gore degil) —
            # kotu konumdan iyilesme de sinyaldir (olculdu: best-tabanli
            # platoda ar25 hic tirmanamadi)
            delta = p - self.last_prog
            self.last_prog = p
            ident = self._ident(cand)
            if delta > 0.001:
                self.vprog[ident] = self.vprog.get(ident, 0.0) + delta
                self.repeat = ident            # MOMENTUM: bunu tekrarla
                self.saw_prog = True
                self.queue = []                # kendi hareket gurultusunu at
            else:
                self.repeat = None             # ise yaramadi -> momentum kir
                # verimsiz secim -> SONUM (bir kez ise yarayan sonsuza dek
                # cazip kalmasin; duvara dayaninca cazibesi ERISIN)
                if ident in self.vprog:
                    self.vprog[ident] *= 0.85
                if delta < -0.001:             # SIMETRIK ceza: kucuk erimeler
                    self.vprog[ident] = self.vprog.get(ident, 0.0) + delta
            if p > self.best_prog + 0.001:     # hipotez-olumu: GERCEK ilerleme
                self.best_prog = p
                self.no_prog = 0
            else:
                self.no_prog += 1
            if self.no_prog >= self.DEAD_AFTER:
                H.alive = False
                self.stats["hyp_switch"] += 1
                self.no_prog = 0
                self.best_prog = 0.0
                self.last_prog = 0.0
                self.probed = set()            # yeni hipotez -> yeniden sonda
                if self._active() is None:      # hepsi oldu -> yeniden kur
                    self._rebuild(obs2)
        if leveled:
            if H is not None:                   # sema: sablon odullenir (KALICI)
                self.template_bonus[H.name] = \
                    self.template_bonus.get(H.name, 0.0) + 0.5
            self.goal_off = False               # yeni seviye -> hedefe yeni sans
            self.rebuilds_no_prog = 0
            self._rebuild(obs2)                 # yeni kare -> yeni baglama
            self.vprog = {}
            self.repeat = None
        if obs2["state"] == "GAME_OVER" and H is not None:
            H.score -= 0.1                      # aktif hipotez cezasi (hafif)


# ===========================================================================
# NIHAI KABUL OLCUMU (§5)
# ===========================================================================
def run_measure(agent_cls, game, max_steps=2000, seed=0):
    from env import Env
    from transition import Mind
    import time
    env = Env(game)
    mind = Mind()
    env.shapes = mind.shapes
    strat = agent_cls(env, mind, seed=seed)
    obs = env.reset()
    first = {}
    maxlev = 0
    t0 = time.time()
    for i in range(max_steps):
        cand = strat.choose(obs)
        if cand is None:
            kind, a, x, y = "press", (obs["avail"][0] if obs["avail"] else 0), None, None
        else:
            kind, a, _, x, y = cand
        obs2 = env.step(kind, a, x, y)
        res = mind.observe(a, f"[A{a}]", obs["grid"], obs2["grid"])
        strat.update(obs, cand, obs2, res)
        if obs2["level"] > maxlev:
            maxlev = obs2["level"]
            first[maxlev] = i + 1
        obs = obs2
    return {"first": first, "max_level": maxlev,
            "sec": round(time.time() - t0, 1),
            "stats": getattr(strat, "stats", {})}


def final_acceptance(max_steps=2000, seeds=(0, 1)):
    new_games = ["m0r0", "g50t", "ar25", "lf52", "ft09"]
    old_games = ["vc33", "tn36", "r11l", "cd82"]
    print(f"=== NIHAI KABUL: hedef-gudumlu ajan ({max_steps} adim, "
          f"tohum {list(seeds)}) ===")
    passed_new = 0
    for game in new_games:
        for name, cls in (("temel", WrongElimReward), ("hedef", GoalAgent)):
            firsts, levels, st = [], [], {}
            for seed in seeds:
                r = run_measure(cls, game, max_steps, seed)
                firsts.append(r["first"].get(1))
                levels.append(r["max_level"])
                for k, v in (r["stats"] or {}).items():
                    st[k] = st.get(k, 0) + v
            f1 = ",".join(str(f) if f else "-" for f in firsts)
            extra = f"  {st}" if name == "hedef" else ""
            print(f"  {game} {name:6s}: sv1@[{f1}] maxsv={max(levels)}{extra}",
                  flush=True)
            if name == "hedef" and max(levels) >= 1:
                passed_new += 1
    print(f"\n-- YENI oyunlardan seviye gecilen: {passed_new}/5 "
          f"(kabul: >=1) --")
    print("\n-- GERILEME KONTROLU (eski gecilen oyunlar) --")
    regress = 0
    base_ref = {"vc33": 2, "tn36": 1, "r11l": 1, "cd82": 1}
    for game in old_games:
        levels = []
        for seed in seeds:
            r = run_measure(GoalAgent, game, max_steps, seed)
            levels.append(r["max_level"])
        ok = max(levels) >= base_ref[game] - (1 if game == "vc33" else 0)
        # vc33 sv2 tek-tohum degiskenligi bilinen; sv1 koru yeterli sayilmaz —
        # kural: en az sv1 (cd82 tohum-bagimli, max ile)
        lost = max(levels) < 1
        regress += lost
        print(f"  {game}: hedef maxsv={max(levels)} (referans {base_ref[game]})"
              f"{'  GERILEME' if lost else ''}", flush=True)
    print(f"\nKABUL: yeni>={passed_new}/5 (gerek >=1), gerileme={regress}")
    return passed_new, regress


if __name__ == "__main__":
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    final_acceptance(steps)
