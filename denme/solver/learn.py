#!/usr/bin/env python3
"""FAZ 1 — MaxSAT ile kural ogrenme (sartname 2.4/2.5 birebir).

Kural formu:  EGER <yuklemlerin VE'si> ISE  E olur.
Amac: tum gozlemlerle tutarli EN KISA kosul (minimum set cover, Z3 Optimize).

  b_j = "j. yuklem kosulda VAR"
  Adim A: J = tum POZITIFLERDE dogru olan yuklemler (aday daraltma)
  Adim B: her NEGATIF icin  OR_{j in J, p[j]=0} b_j   (negatifte ateslememe)
  Adim C: minimize Σ b_j
"""
import hashlib
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from z3 import Optimize, Bool, Or, Not, If, sat  # noqa: E402
from predicates import NAMES                      # noqa: E402

_CACHE = {}          # (etiket, veri-hash) -> (rule, status)   [ayni gozlem kumesi tekrar cozulmesin]


def _data_hash(positives, negatives):
    h = hashlib.sha1()
    for p in positives:
        h.update(b"P" + bytes(p))
    for p in negatives:
        h.update(b"N" + bytes(p))
    return h.hexdigest()


def learn_rule(positives, negatives, pred_names=NAMES, timeout_ms=5000):
    """-> (secili yuklem indeksleri | None, durum)
    durum: ok | ok_trivial | no_candidate_predicates | unseparable | unsat | timeout"""
    N = len(pred_names)
    J = [j for j in range(N) if all(p[j] for p in positives)]
    if not J:
        return None, "no_candidate_predicates"
    if not negatives:
        return [], "ok_trivial"                    # negatif yok -> bos kosul yeter

    b = {j: Bool(f"b_{j}") for j in J}
    o = Optimize()
    o.set("timeout", timeout_ms)

    for p in negatives:
        lits = [b[j] for j in J if not p[j]]
        if not lits:
            return None, "unseparable"             # havuz bu ayrimi IFADE EDEMIYOR -> logla
        o.add(Or(lits))

    o.minimize(sum(If(b[j], 1, 0) for j in J))

    r = o.check()
    if r != sat:
        return None, "timeout" if str(r) == "unknown" else "unsat"
    m = o.model()
    return sorted(j for j in J if m.evaluate(b[j], model_completion=True)), "ok"


def learn_rule_cached(tag, positives, negatives, pred_names=NAMES, timeout_ms=5000):
    """Ayni gozlem kumesi icin cozumu cache'le (9 saat butcesi — sartname §6)."""
    key = (tag, _data_hash(positives, negatives))
    if key not in _CACHE:
        _CACHE[key] = learn_rule(positives, negatives, pred_names, timeout_ms)
    return _CACHE[key]


def second_rule(positives, negatives, b_star, pred_names=NAMES, timeout_ms=5000):
    """FAZ 2 (sartname 3.1): b*'a engelleme clause + maliyet <= c+1 ile IKINCI hipotez."""
    if b_star is None:
        return None, "no_first"
    N = len(pred_names)
    J = [j for j in range(N) if all(p[j] for p in positives)]
    if not J:
        return None, "no_candidate_predicates"

    b = {j: Bool(f"b_{j}") for j in J}
    o = Optimize()
    o.set("timeout", timeout_ms)

    for p in negatives:
        lits = [b[j] for j in J if not p[j]]
        if not lits:
            return None, "unseparable"
        o.add(Or(lits))

    # engelleme: secilenlerden en az biri dussun (b* bos kural ise farkli kural imkansiz)
    if b_star:
        o.add(Or([Not(b[j]) for j in b_star if j in b]))
    else:
        return None, "first_trivial"
    # maliyet siniri: neredeyse ayni sadelik
    o.add(sum(If(b[j], 1, 0) for j in J) <= len(b_star) + 1)
    o.minimize(sum(If(b[j], 1, 0) for j in J))

    r = o.check()
    if r != sat:
        # sat degil = b* disinda (c+1 icinde) tutarli hipotez YOK -> kural TEKIL, guven
        return None, "unique"
    m = o.model()
    return sorted(j for j in J if m.evaluate(b[j], model_completion=True)), "ok"


def rule_fires(rule, p):
    return all(p[j] for j in rule)


def ruleset_fires(rules, p):
    return any(rule_fires(r, p) for r in rules)


def learn_ruleset(positives, negatives, pred_names=NAMES, timeout_ms=5000,
                  max_rules=6):
    """KURAL LISTESI (DNF) — ardisik kapsama; her terim Z3 min-conjunction.

    vc33 teshisi: pozitifler birden cok kumeye yayiliyor (AYRIK yapi) -> tek
    VE-kurali ifade EDEMEZ. Cozum: kalan pozitiflerden bir TOHUM sec, onu tum
    negatiflerden ayiran EN KISA kurali coz (learn_rule, pozitif={tohum}),
    kapsadigi pozitifleri dus, tekrarla. Tahmin: HERHANGI kural ateslerse E.

    AYNI vektor hem pozitif hem negatifse hicbir mantik ayiramaz (gizli durum /
    determinizm-disi) -> o vektorler GURULTU sayilir, ikisinden de cikar, raporlanir.
    -> (rules, info)  info = {noise_pos, noise_neg, uncovered, statuses}
    """
    posc, negc = {}, {}
    for p in positives:
        posc[bytes(p)] = posc.get(bytes(p), 0) + 1
    for p in negatives:
        negc[bytes(p)] = negc.get(bytes(p), 0) + 1
    conflict = set(posc) & set(negc)
    noise_pos = sum(posc[b] for b in conflict)
    noise_neg = sum(negc[b] for b in conflict)
    pos = [list(b) for b in posc if b not in conflict]        # tekil vektorler
    neg = [list(b) for b in negc if b not in conflict]

    rules, statuses, seeds = [], [], []
    remaining = list(pos)
    while remaining and len(rules) < max_rules:
        seed = remaining[0]
        rule, st = learn_rule([seed], neg, pred_names, timeout_ms)
        statuses.append(st)
        if rule is None:                       # tohum ayrilamiyor -> gurultuye at
            remaining = remaining[1:]
            noise_pos += 1
            continue
        covered = [p for p in remaining if rule_fires(rule, p)]
        remaining = [p for p in remaining if not rule_fires(rule, p)]
        if not covered:                        # guvenlik (olmamali)
            remaining = remaining[1:]
        rules.append(rule)
        seeds.append(seed)
    info = {"noise_pos": noise_pos, "noise_neg": noise_neg,
            "uncovered": len(remaining), "statuses": statuses,
            "n_conflict_vec": len(conflict), "seeds": seeds, "negs": neg}
    return rules, info


def describe_rule(rule):
    return " VE ".join(NAMES[j] for j in rule) if rule else "(bos kosul — her zaman)"


# ===========================================================================
# FAZ 1 OLCUM — vc33'te %80/%20 (zamansal bolme), kabul kriterleri
# ===========================================================================
def phase1_measure(game="vc33", steps=1500, seed=0, min_pos=8, timeout_ms=5000):
    from collect import collect, EFFECT_NAME
    print(f"=== FAZ 1 OLCUM: {game}, {steps} adim, tohum={seed} ===")
    t0 = time.time()
    rows, pool, info = collect(game, steps, seed=seed)
    print(f"toplama: {info['n_rows']} satir, max_seviye={info['max_level']}, "
          f"{round(time.time() - t0, 1)} sn")

    cut = int(len(rows) * 0.8)                       # zamansal bolme (sizinti yok)
    train, test = rows[:cut], rows[cut:]

    effects = sorted({e for r in rows for e in r["effects"]})
    results = []
    unsep = 0
    for E in effects:
        pos = [r["p"] for r in train if E in r["effects"]]
        neg = [r["p"] for r in train if E not in r["effects"]]
        if len(pos) < min_pos or not neg:
            continue
        # POLARITE: cogunluk sinifini varsayilan yap, AZINLIGI ogren.
        # (neredeyse-hep-olan etkide "E olur" kurali 1000+ pozitifi kapsayamaz;
        #  dogru soru "NE ZAMAN OLMAZ".)
        inverted = len(pos) > len(neg)
        if inverted:
            pos, neg = neg, pos
        t1 = time.time()
        # once TEK kural dene (sartname cekirdegi); olmazsa KURAL LISTESI (DNF)
        rule, st = learn_rule(pos, neg, timeout_ms=timeout_ms)
        if rule is not None:
            rules, rinfo = [rule], {"noise_pos": 0, "noise_neg": 0, "uncovered": 0}
        else:
            if st == "unseparable":
                unsep += 1
            rules, rinfo = learn_ruleset(pos, neg, timeout_ms=timeout_ms)
            st = f"{st}->liste[{len(rules)}]"
        dt = time.time() - t1
        if not rules:
            results.append({"E": E, "status": st, "sec": dt})
            print(f"  E={E:>2} ({EFFECT_NAME.get(E, '?')}): {st}  [{dt:.2f}sn]")
            continue
        tp = fp_ = tn = fn = 0
        for r in test:
            fired = ruleset_fires(rules, r["p"])
            if inverted:                       # kural "E OLMAZ"i yakaliyor
                fired = not fired
            truth = E in r["effects"]
            tp += fired and truth
            fp_ += fired and not truth
            tn += (not fired) and (not truth)
            fn += (not fired) and truth
        n = max(tp + fp_ + tn + fn, 1)
        acc = (tp + tn) / n
        maxlen = max(len(r_) for r_ in rules)
        results.append({"E": E, "status": st, "rules": rules, "len": maxlen,
                        "n_rules": len(rules), "acc": acc, "tp": tp, "fp": fp_,
                        "tn": tn, "fn": fn, "sec": dt, "n_pos": len(pos),
                        "n_neg": len(neg), "rinfo": rinfo, "inverted": inverted})
        yz = "E-OLMAZ" if inverted else "E-olur"
        print(f"  E={E:>2} ({EFFECT_NAME.get(E, '?'):9s}) [{yz}]: {len(pos):4d}p/"
              f"{len(neg):4d}n  {len(rules)} kural (en uzun {maxlen})  "
              f"gurultu p{rinfo['noise_pos']}/n{rinfo['noise_neg']}  [{dt:.2f}sn]")
        for r_ in rules:
            print(f"        EGER {describe_rule(r_)}")
        print(f"        test dogruluk={acc:.3f} (tp{tp} fp{fp_} tn{tn} fn{fn})")

    # kabul: ogrenilen kurallarda >=%80 dogruluk, terim uzunlugu<=5, sure<5sn
    ok_rules = [r for r in results if r.get("rules")]
    passed = [r for r in ok_rules if r["acc"] >= 0.8 and r["len"] <= 5 and r["sec"] < 5]
    print(f"\nKABUL: {len(passed)}/{len(ok_rules)} ogrenilen kural kriteri gecti "
          f"(dogruluk>=0.80, terim<=5 yuklem, sure<5sn) | tek-kural unseparable={unsep}")
    return results, {"passed": len(passed), "learned": len(ok_rules),
                     "unseparable": unsep, "info": info}


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "vc33"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    phase1_measure(game, steps)
