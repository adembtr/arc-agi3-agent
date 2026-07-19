#!/usr/bin/env python3
"""Ajanin GOZ (perception) + EL (action) birlikte — gercek oyunda.

  python demo_goz_el.py <oyun>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P     # noqa: E402
from action import Hand    # noqa: E402


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else "lf52"
    h = Hand(game)
    grid = h.last["grid"]

    print(f"================  {game}  ================")
    print(f"durum={h.last['state']}  seviye={h.last['levels_completed']}"
          f"/{h.last['win_levels']}  gecerli={h.last['available']}"
          f"  (animasyon {h.last['n_frames']} kare)")

    print("\n---  GOZ: ne goruyor  ---")
    print(P.summarize(grid))

    # sekil iliskileri ozeti
    objs = P.find_objects(grid)
    pairs = {"ayni": 0, "ayna": 0, "donmus": 0, "olcekli": 0}
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i], objs[j]
            if a.color != b.color:
                continue
            if P.same_shape(a, b):
                pairs["ayni"] += 1
            elif P.is_mirror(a, b):
                pairs["ayna"] += 1
            elif P.is_rotation(a, b):
                pairs["donmus"] += 1
            elif P.similar_scaled(a, b):
                pairs["olcekli"] += 1
    print(f"  sekil iliskileri (ayni renk): ayni={pairs['ayni']} "
          f"ayna={pairs['ayna']} donmus={pairs['donmus']} olcekli={pairs['olcekli']}")

    print("\n---  EL: ne biliyor  ---")
    for a, usable, tag in h.what_i_know():
        mark = "✓ gecerli" if usable else "· su an yok"
        print(f"  [{mark:>10}] A{a}: {tag}")


if __name__ == "__main__":
    main()
