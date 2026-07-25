#!/usr/bin/env python3
"""FAZ 2 — CEGIS ile deney secimi (sartname §3).

Dongu:
  1. Gozlemlerle en kisa kural(lar)i coz          -> R1   (learn_ruleset)
  2. Ikinci en kisa tutarli hipotezi coz          -> R2   (second_rule; ilk terim)
  3. R2 yoksa -> kural TEKIL, GUVEN. Somuruye gec.
  4. R1 ve R2'nin AYRILDIGI aday aksiyonu bul     -> a*
  5. a* oyna (sonuc iki hipotezden birini KESIN oldurur), havuza ekle
  6. 1'e don (yeni satir birikince / tahmin sasinca yeniden ogren)

Karar oncelik sirasi (her adim):
  GUVENLIK: GAMEOVER kurali ateslenen adaylar elenir (yedekte serbest)
  SOMURU:   WIN(seviye) kurali ateslenen aday -> hemen oyna
  DENEY:    R1 != R2 ayrisan aday -> oyna (bilgi kazanci)
  YEDEK:    WrongElimReward (yanlis-eleme + Go-Explore) — sartname §5/§6

Cozucu ASLA donduramaz: her Z3 cagrisinda timeout + toplam butce; butce
asilirsa cozucu kapanir, saf yanlis-eleme surer.
"""
import sys
import os
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", "infra"))

import transition as T                                   # noqa: E402
from strategies2 import WrongElimReward                  # noqa: E402
from predicates import PredicatePool, SMALL              # noqa: E402
from learn import (learn_ruleset, second_rule, rule_fires,  # noqa: E402
                   ruleset_fires, describe_rule)
from collect import E_GAMEOVER                           # noqa: E402

E_WIN = T.E_WIN
E_STRUCT = 11        # turetilmis etiket: adimda HERHANGI yapisal degisim oldu mu


class CegisAgent(WrongElimReward):
    """Cozucu-ustte, yanlis-eleme-yedekli ajan."""
    RELEARN_MIN = 8            # surpriz varsa bu kadar yeni satirda yeniden ogren
    RELEARN_MAX = 30           # surpriz olmasa da bu kadar satirda bir tazele
    MIN_POS = 3                # kural ogrenmek icin en az pozitif
    SOLVER_BUDGET = 120.0      # toplam z3 saniyesi (asilirsa cozucu KAPANIR)
    Z3_TIMEOUT_MS = 2000
    # deney onceligi: hedefe yakin etkiler once. GAMEOVER deneyi YASAK (intihar olur).
    EXPERIMENT_TARGETS = (E_WIN, T.E_MERGE, T.E_RECOLOR, T.E_VANISH,
                          T.E_APPEAR, T.E_MOVE)
    LEARN_TARGETS = EXPERIMENT_TARGETS + (E_GAMEOVER, E_STRUCT)
    EXP_PER_LEVEL = 8          # seviye basina deney butcesi (ablasyon: sinirsiz deney
    EXP_MIN_IDLE = 2           # sv2'yi kaybettirdi); deney = ancak bosta gezerken

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pool = PredicatePool()
        self.rows = []                 # {p, action, effects}
        self.models = {}               # E -> {rules, inverted, info}
        self.alt = {}                  # E -> ikinci hipotez ilk-terimi | None(=tekil)
        self.new_rows = 0
        self.surprise = False
        self.version = 0               # kural seti surumu (tekrar-deneme kontrolu)
        self.tried_exploit = set()     # (fp, ident, version)
        self.tried_exp = set()         # (fp, ident, E, version)
        self.solver_spent = 0.0
        self.solver_on = True
        self.exp_this_level = 0
        self.stats = {"exploit": 0, "experiment": 0, "fallback": 0,
                      "safety_veto": 0, "dead_skip": 0, "relearn": 0,
                      "unseparable": 0}

    # ---------- kodlama ----------
    def _focus(self, obs, cd):
        if cd[0] != "click":
            return None
        for ob in obs["objs"]:
            if ob.size > SMALL:
                continue
            cy, cx = ob.centroid
            if (int(round(cx)), int(round(cy))) == (cd[3], cd[4]):
                return ob
        return None

    def _pvec(self, obs, cd):
        return self.pool.encode(obs, cd[1], self._focus(obs, cd))

    # ---------- tahmin ----------
    def _predicts(self, E, p):
        m = self.models.get(E)
        if not m or not m["rules"]:
            return None                          # model yok -> bilinmiyor
        fired = ruleset_fires(m["rules"], p)
        return (not fired) if m["inverted"] else fired

    # ---------- ogrenme ----------
    def _relearn(self):
        if not self.solver_on:
            return
        t0 = time.time()
        for E in self.LEARN_TARGETS:
            pos = [r["p"] for r in self.rows if E in r["effects"]]
            neg = [r["p"] for r in self.rows if E not in r["effects"]]
            if len(pos) < self.MIN_POS or not neg:
                continue
            inverted = len(pos) > len(neg)
            if inverted:
                pos, neg = neg, pos
            rules, info = learn_ruleset(pos, neg, timeout_ms=self.Z3_TIMEOUT_MS)
            self.stats["unseparable"] += info["statuses"].count("unseparable")
            self.models[E] = {"rules": rules, "inverted": inverted, "info": info}
            # ikinci hipotez (ilk terim uzerinden): yoksa kural TEKIL -> guven
            if rules and info["seeds"]:
                alt, st = second_rule([info["seeds"][0]], info["negs"], rules[0],
                                      timeout_ms=self.Z3_TIMEOUT_MS)
                self.alt[E] = alt if st == "ok" else None
            else:
                self.alt[E] = None
        self.version += 1
        self.new_rows = 0
        self.surprise = False
        self.stats["relearn"] += 1
        self.solver_spent += time.time() - t0
        if self.solver_spent > self.SOLVER_BUDGET:
            self.solver_on = False               # butce bitti -> saf yanlis-eleme

    # ---------- karar ----------
    def choose(self, obs):
        if self.forced or self.queue or not self.solver_on:
            return super().choose(obs)
        c = self.cands(obs)
        if not c:
            return None
        if self.new_rows >= self.RELEARN_MAX or \
                (self.surprise and self.new_rows >= self.RELEARN_MIN):
            self._relearn()

        pv = [(cd, self._pvec(obs, cd)) for cd in c]

        # 1) GUVENLIK: GAMEOVER tahmini olan adaylari ele.
        #    KAPILI: az veriyle asiri-genel kural dogru hamleyi de engeller (vc33
        #    seviye-2 gerilemesi boyle cikti). Sartlar: >=5 GO pozitifi, terim >=2
        #    yuklem, ve ilerleme tikanmissa (since_new) veto tamamen devre disi.
        m_go = self.models.get(E_GAMEOVER)
        if m_go and m_go["rules"] and not m_go["inverted"] \
                and self.since_new < 12:
            n_go = sum(1 for r in self.rows if E_GAMEOVER in r["effects"])
            strong = [r_ for r_ in m_go["rules"] if len(r_) >= 2]
            if n_go >= 5 and strong:
                safe = [(cd, p) for cd, p in pv
                        if not any(rule_fires(r_, p) for r_ in strong)]
                if safe and len(safe) < len(pv):
                    self.stats["safety_veto"] += len(pv) - len(safe)
                if safe:
                    pv = safe

        # 2) OLU-HAMLE ATLAMA: "yapisal etki OLMAZ" tahminli adaylari atla.
        #    Temel yontem her olu hamleyi durum basina BIR KEZ deneyip ogrenir;
        #    cozucu kural genellemesiyle DENEMEDEN atlar = aksiyon tasarrufu
        #    (skor formulu: her aksiyon karesel ceza). Tikaninca devre disi.
        if self.since_new < 12:
            alive = [(cd, p) for cd, p in pv
                     if self._predicts(E_STRUCT, p) is not False]
            if alive and len(alive) < len(pv):
                self.stats["dead_skip"] += len(pv) - len(alive)
                pv = alive

        # 3) SOMURU: WIN kurali ateslenen aday
        for cd, p in pv:
            if self._predicts(E_WIN, p):
                key = (obs["fp"], self._ident(cd), self.version)
                if key not in self.tried_exploit:
                    self.tried_exploit.add(key)
                    self.stats["exploit"] += 1
                    return self._commit(cd)

        # 4) DENEY (CEGIS): R1 ve R2'nin ayrildigi aday.
        #    KAPILI: sicak seride hamle CALMAZ (ablasyon: sinirsiz deney sv2
        #    kaybettirdi). Sadece bosta gezerken + seviye basina butce.
        if self.since_new >= self.EXP_MIN_IDLE \
                and self.exp_this_level < self.EXP_PER_LEVEL:
            for E in self.EXPERIMENT_TARGETS:
                m, alt = self.models.get(E), self.alt.get(E)
                if not m or not m["rules"] or alt is None:
                    continue
                r1_term = m["rules"][0]
                for cd, p in pv:
                    if rule_fires(r1_term, p) != rule_fires(alt, p):
                        key = (obs["fp"], self._ident(cd), E, self.version)
                        if key in self.tried_exp:
                            continue
                        self.tried_exp.add(key)
                        self.stats["experiment"] += 1
                        self.exp_this_level += 1
                        return self._commit(cd)

        # 5) YEDEK: yanlis-eleme + Go-Explore
        self.stats["fallback"] += 1
        return super().choose(obs)

    def _commit(self, cd):
        """super().choose disi secimlerde traj'i elle isle (arsiv tutarliligi)."""
        mv = (("click", 6, cd[2], cd[3], cd[4]) if cd[0] == "click"
              else ("press", cd[1], -1, None, None))
        self.traj.append(mv)
        return cd

    # ---------- gozlem ----------
    def update(self, obs, cand, obs2, res):
        super().update(obs, cand, obs2, res)
        if cand is None or cand[1] == 0:
            return
        eff = {ch["effect"] for ch in res["changes"]
               if ch["effect"] != T.E_NOCHANGE}
        if eff:
            eff.add(E_STRUCT)                  # turetilmis: yapisal degisim var
        if obs2["level"] > obs["level"]:
            eff.add(E_WIN)
            self.exp_this_level = 0            # yeni seviye -> deney butcesi tazele
        if obs2["state"] == "GAME_OVER":
            eff.add(E_GAMEOVER)
        if not eff:
            eff = {T.E_NOCHANGE}
        p = self._pvec(obs, cand)
        self.rows.append({"p": p, "action": cand[1], "effects": frozenset(eff)})
        # nesne satirlari (tus aksiyonu): "yol varsa hareket" tipi kurallar icin
        if cand[0] == "press":
            for ob in obs["objs"]:
                if ob.size > SMALL:
                    continue
                cells = set(ob.cells)
                oeff = set()
                for ch in res["changes"]:
                    b = ch.get("before")
                    if b is not None and ch["effect"] != T.E_NOCHANGE \
                            and cells & set(b.cells):
                        oeff.add(ch["effect"])
                if oeff:
                    oeff.add(E_STRUCT)
                self.rows.append({"p": self.pool.encode(obs, cand[1], ob),
                                  "action": cand[1],
                                  "effects": frozenset(oeff or {T.E_NOCHANGE})})
        self.new_rows += 1
        # SURPRIZ: mevcut model bu satiri yanlis tahmin etti mi? (CEGIS tetigi)
        for E in self.LEARN_TARGETS:
            pred = self._predicts(E, p)
            if pred is not None and pred != (E in eff):
                self.surprise = True
                break


# ===========================================================================
# FAZ 2 OLCUM — seviyeye-kadar-aksiyon: temel (yanlis-eleme) vs CEGIS
# ===========================================================================
def run_measure(agent_cls, game, max_steps=2000, seed=0):
    from env import Env
    from transition import Mind
    env = Env(game)
    mind = Mind()
    env.shapes = mind.shapes
    strat = agent_cls(env, mind, seed=seed)
    obs = env.reset()
    first = {}                     # seviye -> kacinci aksiyonda
    maxlev = 0
    t0 = time.time()
    for i in range(max_steps):
        cand = strat.choose(obs)
        if cand is None:
            kind, a, x, y = "press", (obs["avail"][0] if obs["avail"] else 0), None, None
        else:
            kind, a, _, x, y = cand
        before = obs["grid"]
        obs2 = env.step(kind, a, x, y)
        res = mind.observe(a, f"[A{a}]", before, obs2["grid"])
        strat.update(obs, cand, obs2, res)
        if obs2["level"] > maxlev:
            maxlev = obs2["level"]
            first[maxlev] = i + 1
        obs = obs2
    stats = getattr(strat, "stats", {})
    return {"first": first, "max_level": maxlev, "sec": round(time.time() - t0, 1),
            "stats": stats}


def phase2_measure(games=("vc33", "tn36", "r11l", "cd82"), seeds=(0, 1),
                   max_steps=2000):
    print(f"=== FAZ 2 OLCUM: seviye-1'e-kadar-aksiyon, {max_steps} adim, "
          f"tohum={list(seeds)} ===")
    table = {}
    for game in games:
        row = {}
        for name, cls in (("temel", WrongElimReward), ("cegis", CegisAgent)):
            firsts, levels = [], []
            st_acc = {}
            for seed in seeds:
                r = run_measure(cls, game, max_steps, seed)
                firsts.append(r["first"].get(1))
                levels.append(r["max_level"])
                for k, v in (r["stats"] or {}).items():
                    st_acc[k] = st_acc.get(k, 0) + v
            got = [f for f in firsts if f is not None]
            row[name] = {"first1": got, "mean": (sum(got) / len(got)) if got else None,
                         "max_level": max(levels), "stats": st_acc}
            f1 = ",".join(str(f) if f else "-" for f in firsts)
            extra = (f"  [somuru={st_acc.get('exploit', 0)} deney="
                     f"{st_acc.get('experiment', 0)} veto={st_acc.get('safety_veto', 0)}"
                     f" olu-atla={st_acc.get('dead_skip', 0)}"
                     f" unsep={st_acc.get('unseparable', 0)}]" if name == "cegis" else "")
            print(f"  {game} {name:6s}: sv1@[{f1}] maxsv={max(levels)}{extra}",
                  flush=True)
        table[game] = row

    # kabul degerlendirme
    print("\n--- KABUL (>=2 oyunda >=%25 daha az aksiyon, hic seviye kaybi yok) ---")
    better = 0
    regress = 0
    for game, row in table.items():
        b, c = row["temel"], row["cegis"]
        if c["max_level"] < b["max_level"]:
            regress += 1
            print(f"  {game}: SEVIYE KAYBI ({b['max_level']} -> {c['max_level']})")
            continue
        if b["mean"] and c["mean"]:
            gain = 1 - c["mean"] / b["mean"]
            better += gain >= 0.25
            print(f"  {game}: temel {b['mean']:.0f} vs cegis {c['mean']:.0f} aksiyon "
                  f"(kazanc %{100 * gain:.0f})")
        elif c["mean"] and not b["mean"]:
            better += 1
            print(f"  {game}: temel GECEMEDI, cegis {c['mean']:.0f} aksiyonda gecti")
        elif b["mean"] and not c["mean"]:
            print(f"  {game}: cegis GECEMEDI (temel {b['mean']:.0f})")
        else:
            print(f"  {game}: ikisi de gecemedi")
    verdict = "GECTI" if (better >= 2 and regress == 0) else "GECEMEDI"
    print(f"KABUL: {verdict} (daha-iyi={better}/{len(table)}, gerileme={regress})")
    return table, verdict


if __name__ == "__main__":
    games = sys.argv[1].split(",") if len(sys.argv) > 1 else \
        ["vc33", "tn36", "r11l", "cd82"]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    phase2_measure(games, max_steps=steps)
