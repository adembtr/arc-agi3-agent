#!/usr/bin/env python3
"""Birim testler — cozucu katmani. Calistir:
   cd denme && uv run --project ../ARC-AGI-3-Agents python solver/test_solver.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from learn import (learn_rule, learn_ruleset, second_rule, rule_fires,  # noqa: E402
                   ruleset_fires)
from predicates import NAMES, N, PredicatePool                          # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  OK   {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def vec(true_idx):
    p = [False] * N
    for j in true_idx:
        p[j] = True
    return p


def test_learn_rule():
    print("learn_rule:")
    # tek yuklem ayirir: pozitiflerde 0+1, negatiflerde sadece 0 -> kural=[1]
    pos = [vec([0, 1, 2]), vec([0, 1, 3])]
    neg = [vec([0, 2]), vec([0, 3])]
    rule, st = learn_rule(pos, neg)
    check("tek-yuklem min kural", st == "ok" and rule == [1])
    # EN KISA'yi secer: {1,2} de ayirir ama tek basina 1 yeter
    check("occam (1 yuklem yeter)", len(rule) == 1)
    # negatif yok -> bos kural
    rule, st = learn_rule(pos, [])
    check("negatifsiz bos kural", st == "ok_trivial" and rule == [])
    # ayni vektor iki tarafta -> unseparable
    same = vec([0, 1])
    rule, st = learn_rule([same], [same])
    check("unseparable tespiti", rule is None and st == "unseparable")
    # aday yok: pozitiflerin kesisimi bos
    rule, st = learn_rule([vec([1]), vec([2])], [vec([3])])
    check("no_candidate_predicates", st == "no_candidate_predicates")
    # iki-yuklemli zorunlu kural: negatifler tek tek tasiyor
    pos = [vec([0, 1, 2])]
    neg = [vec([0, 1]), vec([0, 2]), vec([1, 2])]
    rule, st = learn_rule(pos, neg)
    check("cok-yuklem gerekince bulur",
          st == "ok" and all(rule_fires(rule, p) is False for p in neg)
          and rule_fires(rule, pos[0]))


def test_ruleset():
    print("learn_ruleset (DNF):")
    # AYRIK yapi: pozitifler ya yuklem-1 ya yuklem-2 (tek VE ifade edemez)
    pos = [vec([0, 1]), vec([0, 2])]
    neg = [vec([0, 3]), vec([0])]
    single, st = learn_rule(pos, neg)
    check("tek kural ayrik yapida unseparable", single is None)
    rules, info = learn_ruleset(pos, neg)
    check("liste ayrik yapiyi ogrenir",
          len(rules) >= 2 and all(ruleset_fires(rules, p) for p in pos)
          and not any(ruleset_fires(rules, p) for p in neg))
    # celiskili (ayni vektor iki tarafta) -> gurultu sayilir, kalanlar ogrenilir
    same = vec([0, 5])
    rules, info = learn_ruleset(pos + [same], neg + [same])
    check("celiski gurultuye atilir",
          info["noise_pos"] == 1 and info["noise_neg"] == 1
          and all(ruleset_fires(rules, p) for p in pos))


def test_second_rule():
    print("second_rule (CEGIS ikinci hipotez):")
    # iki esdeger aciklama: yuklem 1 VEYA yuklem 2 (her pozitifte ikisi de var)
    pos = [vec([0, 1, 2])]
    neg = [vec([0, 3])]
    r1, st1 = learn_rule(pos, neg)
    r2, st2 = second_rule(pos, neg, r1)
    check("ikinci hipotez bulunur", st2 == "ok" and r2 is not None and r2 != r1)
    check("ikisi de veriyle tutarli",
          rule_fires(r2, pos[0]) and not rule_fires(r2, neg[0]))
    # ayrisan girdi VAR: r1={1} icin vec([1]) atesler, r2={2} icin ateslemez
    probe = vec([r1[0]])
    check("hipotezler bir girdide ayrisir",
          rule_fires(r1, probe) != rule_fires(r2, probe))
    # tekil kural: baska aciklama yoksa 'unique'
    pos = [vec([7])]
    neg = [vec([8])]
    r1, _ = learn_rule(pos, neg)          # sadece yuklem-7 aday
    r2, st = second_rule(pos, neg, r1)
    check("tekil kuralda unique", r2 is None and st == "unique")


def test_predicates():
    print("predicates:")
    pool = PredicatePool()
    check("isim listesi sabit uzunluk", len(pool.predicate_names()) == N)
    # slot kaydi deterministik: ayni kume ayni slot
    s1 = pool._slot_of(42)
    s2 = pool._slot_of(42)
    s3 = pool._slot_of(99)
    check("kume-slot kararli", s1 == s2 and s3 == s1 + 1)


def test_cegis_agent_smoke():
    print("CegisAgent (duman):")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from cegis import run_measure, CegisAgent
    r = run_measure(CegisAgent, "vc33", 120, seed=0)
    check("120 adim cokusmeden kosar", r["max_level"] >= 0 and r["sec"] < 120)
    check("istatistik doner", "fallback" in r["stats"])


if __name__ == "__main__":
    test_learn_rule()
    test_ruleset()
    test_second_rule()
    test_predicates()
    test_cegis_agent_smoke()
    print(f"\nTOPLAM: {PASS} OK, {FAIL} FAIL")
    sys.exit(1 if FAIL else 0)
