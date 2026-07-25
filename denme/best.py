#!/usr/bin/env python3
"""SECILEN YONTEM: Go-Explore (13 yontem icinde en iyi keşif — bkz REPORT.md).

Saf algoritma: arsivle + umut veren duruma reset&replay ile don + oradan kesfet.
Reset-only ortamimizla dogal uyum. LLM/insan-izi/onceden-egitilmis model YOK.

DURUST NOT: bu bile tek basina seviye GECMIYOR (REPORT.md). Sonraki adim: arsivden
tek aksiyon degil AKSIYON-CIFTI/DIZI (makro) dene — asil eksik bu.

Calistir:  uv run --project .../ARC-AGI-3-Agents python best.py <oyun> <adim>
"""
import sys
sys.path.insert(0, "infra")
import bench
from strategies import GoExplore


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else "m0r0"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    m = bench.run(GoExplore, game, steps, seed=0)
    print(f"Go-Explore  {game}  {steps} adim:")
    for k, v in m.items():
        print(f"  {k:12s} = {v}")


if __name__ == "__main__":
    main()
