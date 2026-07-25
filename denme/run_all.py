#!/usr/bin/env python3
"""13 yontemi oyunlarda calistir, metrikleri topla, SIRALA, rapor yaz.
Kullanim: uv run --project .../ARC-AGI-3-Agents python run_all.py <adim> <tekrar>
"""
import sys
import json
sys.path.insert(0, "infra")
import bench
import strategies

STEPS = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
REPEAT = int(sys.argv[2]) if len(sys.argv) > 2 else 2
GAMES = ["lf52", "m0r0", "ft09"]        # click + kb-click + none (cesitlilik)


def avg(dicts):
    keys = dicts[0].keys()
    return {k: round(sum(d[k] for d in dicts) / len(dicts), 2) for k in keys}


def main():
    results = {}
    for name in sorted(strategies.ALL):
        per_game = {}
        for game in GAMES:
            runs = []
            for r in range(REPEAT):
                m = bench.run(strategies.ALL[name], game, STEPS, seed=r)
                runs.append(m)
            per_game[game] = avg(runs)
        # toplam skor = oyunlar ortalamasi
        total = sum(bench.score_metrics(per_game[g]) for g in GAMES) / len(GAMES)
        results[name] = {"skor": round(total, 1), "oyunlar": per_game}
        print(f"[bitti] {name}: skor={round(total,1)}  "
              f"lf52-lvl={per_game['lf52']['max_level']} "
              f"kapsam={per_game['lf52']['coverage']} "
              f"birlesme={sum(per_game[g]['merges'] for g in GAMES)}")
        sys.stdout.flush()

    ranked = sorted(results.items(), key=lambda kv: -kv[1]["skor"])
    print("\n" + "=" * 60)
    print("SIRALAMA (skor = seviye*1000 + birlesme*20 + hedef*10 + kapsam*0.1 + olay)")
    print("=" * 60)
    for i, (name, r) in enumerate(ranked, 1):
        print(f"{i:2d}. {name:20s} skor={r['skor']:.1f}")

    with open("SONUCLAR.json", "w") as f:
        json.dump({"steps": STEPS, "repeat": REPEAT, "games": GAMES,
                   "ranked": ranked}, f, ensure_ascii=False, indent=2)
    print("\n-> SONUCLAR.json yazildi")


if __name__ == "__main__":
    main()
