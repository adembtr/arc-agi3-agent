#!/usr/bin/env python3
"""ENTEGRASYON — cozucu-ustte nihai ajan (sartname §5/§8).

Katmanlar:
  algi + sekil-sozlugu  ->  infra/perception + ShapeVocab      (mevcut, dokunulmadi)
  SMT/MaxSAT            ->  gecis kurali ogrenme (learn.py)
  CEGIS                 ->  deney secimi (cegis.py)
  yanlis-eleme          ->  YEDEK (strategies2.WrongElimReward — cozucu donarsa/butce bitince)

Kullanim (bench ile ayni arayuz):
  from solver.agent import SolverAgent
  bench.run(SolverAgent, "vc33", 2000, seed=0)

CLI:
  uv run --project ../ARC-AGI-3-Agents python solver/agent.py vc33 2000
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))

from cegis import CegisAgent, run_measure           # noqa: E402

# Nihai ajan = CEGIS + olu-hamle atlama + GAMEOVER veto + yanlis-eleme yedek.
# (CegisAgent zaten WrongElimReward'i miras alir; cozucu kapaninca saf yedege duser.)
SolverAgent = CegisAgent


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "vc33"
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    r = run_measure(SolverAgent, game, steps, seed)
    print(f"{game}: max_seviye={r['max_level']} seviye-adimlari={r['first']} "
          f"({r['sec']}sn)\n  istatistik={r['stats']}")
