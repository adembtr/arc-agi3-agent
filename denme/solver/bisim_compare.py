import sys
sys.path.insert(0, "solver")
from cegis import run_measure
from strategies2 import WrongElimReward
from bisim import make_bisim_agent

AGENTS = [("esik", WrongElimReward),
          ("bisim-hosgorulu", make_bisim_agent(strict=False)),
          ("bisim-strict", make_bisim_agent(strict=True))]

for game in ["vc33", "tn36", "r11l", "cd82"]:
    for name, cls in AGENTS:
        firsts, levels = [], []
        for seed in (0, 1):
            r = run_measure(cls, game, 2000, seed)
            firsts.append(r["first"].get(1))
            levels.append(r["max_level"])
        f1 = ",".join(str(f) if f else "-" for f in firsts)
        print(f"{game} {name:16s}: sv1@[{f1}] maxsv={max(levels)}", flush=True)
print("BISIM KARSILASTIRMA BITTI")
