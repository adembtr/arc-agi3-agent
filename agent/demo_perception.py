#!/usr/bin/env python3
"""Gercek bir oyun grid'inde perception.py'yi calistir.

Kullanim:  (ARC-AGI-3-Agents venv icinden)
  OPERATION_MODE=offline ENVIRONMENTS_DIR=.../environment_files \
  python demo_perception.py lf52
"""
import os
import sys

os.environ.setdefault("OPERATION_MODE", "offline")
os.environ.setdefault("ENVIRONMENTS_DIR",
                      "/home/adem/Desktop/AGI/environment_files")
os.environ.setdefault("MPLBACKEND", "agg")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P  # noqa: E402
from arc_agi import Arcade  # noqa: E402


def get_grid(game):
    arc = Arcade()
    env = arc.make(game)
    fr = env.reset()
    grid = [[int(v) for v in row] for row in fr.frame[-1]]
    return grid


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else "lf52"
    grid = get_grid(game)
    print(f"=== {game} — SEVIYE 1 baslangic grid'i ===")
    print(P.summarize(grid))

    objs = P.find_objects(grid)
    # en buyuk 6 nesneyi ve iliskilerini goster
    objs.sort(key=lambda o: -o.size)
    print("\n--- en buyuk nesneler ---")
    for i, o in enumerate(objs[:8]):
        r0, c0, r1, c1 = o.bbox
        print(f"  #{i}: renk={o.color:>2} boyut={o.size:>3} "
              f"kutu=({r0},{c0})-({r1},{c1}) {o.height}x{o.width}")

    # ayni-sekil / ayna ornekleri: ayni renkten eslesenler
    print("\n--- 'ayni sekil' iliskileri (isim yok, sadece geometri) ---")
    found = 0
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i], objs[j]
            if a.color == b.color and a.size == b.size:
                if P.same_shape(a, b):
                    print(f"  #{i} ve #{j}: AYNI SEKIL (renk {a.color}, {a.size} hucre)")
                    found += 1
                elif P.is_mirror(a, b):
                    print(f"  #{i} ve #{j}: AYNA goruntusu (renk {a.color})")
                    found += 1
                elif P.same_shape_symmetry(a, b):
                    print(f"  #{i} ve #{j}: ayni sekil (dönme/ayna ile)")
                    found += 1
            if found >= 12:
                break
        if found >= 12:
            break
    if not found:
        print("  (bu grid'de ayni-sekil esi bulunamadi)")


if __name__ == "__main__":
    main()
