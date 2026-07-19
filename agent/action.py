#!/usr/bin/env python3
"""action.py — ARC-AGI-3 EL (aksiyon arayuzu).

Ajanin "eli". Ona ne KESIN bildigimizi, ne TAHMIN ettigimizi verir.
Tahminler hipotezdir: transition.py (diff) ile dogrulanir/curutulur.

Kesin (evrensel, her oyunda ayni):
    0 = RESET  (oyunu tamamen basa alir)
    6 = CLICK  (x,y)'ye tikla

Tahmin (dogrulanacak, oyuna gore degisebilir):
    1,2,3,4 = muhtemelen HAREKET (sag/sol/ileri/geri/yukari/asagi).
              Cogu oyunda ayni ama BAZI oyunlarda etkisiz olabilir.
              Kesin yon SABIT DEGIL -> denemeyle ogrenilir.
    5       = muhtemelen YUMUSAK SIFIRLAMA: reset degil, bir degisiklik
              yaparak basa doner (cogu oyunda TUZAK).
    7       = BILINMIYOR -> kesfedilecek.
"""
from __future__ import annotations
import os

os.environ.setdefault("OPERATION_MODE", "offline")
os.environ.setdefault("ENVIRONMENTS_DIR",
                      "/home/adem/Desktop/AGI/environment_files")
os.environ.setdefault("MPLBACKEND", "agg")

from arc_agi import Arcade          # noqa: E402
from arcengine import GameAction    # noqa: E402


# --- Ajanin aksiyonlar hakkinda "dogustan" bildikleri -----------------------
KNOWN = {
    0: "RESET  — oyunu tamamen basa alir (KESIN, evrensel)",
    6: "CLICK  — (x,y)'ye tikla (KESIN, evrensel)",
}

PRIOR = {  # hipotez: dogrulanacak / curutulecek
    1: "muhtemelen HAREKET (yon belirsiz); bazi oyunlarda etkisiz",
    2: "muhtemelen HAREKET (yon belirsiz); bazi oyunlarda etkisiz",
    3: "muhtemelen HAREKET (yon belirsiz); bazi oyunlarda etkisiz",
    4: "muhtemelen HAREKET (yon belirsiz); bazi oyunlarda etkisiz",
    5: "muhtemelen YUMUSAK-SIFIRLAMA (degisiklikle basa doner) / TUZAK",
    7: "BILINMIYOR — kesfedilecek",
}

# hareket adaylari — YON SABIT DEGIL, sadece "bunlar hareket olabilir" grubu
MOVE_CANDIDATES = (1, 2, 3, 4)
SOFT_RESET_CANDIDATE = 5
CLICK = 6
RESET = 0


def describe(action: int) -> str:
    """Ajanin bir aksiyon hakkinda dogustan bildigi."""
    if action in KNOWN:
        return KNOWN[action]
    return PRIOR.get(action, f"A{action}: tanimsiz")


class Hand:
    """Ajanin eli: bir oyunu tutar, aksiyon uygular, gozlem dondurur.

    Ogrenilen anlamlar `self.learned` icinde birikir (baslangicta bos;
    transition.py dogruladikca doldurulur).
    """

    def __init__(self, game: str):
        self.game = game
        self._arc = Arcade()
        self._env = self._arc.make(game)
        self.learned = {}          # {action: ogrenilen_anlam}  (sonra dolacak)
        self.last = None
        self.reset()

    # --- temel ilkel eylemler ---
    def _obs(self, fr):
        grids = [[[int(v) for v in row] for row in g] for g in fr.frame]
        if not grids:
            # WIN / GAME_OVER -> motor bos frame doner; onceki grid'i koru
            prev = self.last["grid"] if self.last else [[0] * 64 for _ in range(64)]
            grids = [prev]
        obs = {
            "grids": grids,
            "grid": grids[-1],                       # nihai durum
            "n_frames": len(grids),                  # animasyon kare sayisi
            "state": fr.state.name if hasattr(fr.state, "name") else str(fr.state),
            "levels_completed": getattr(fr, "levels_completed", 0),
            "win_levels": getattr(fr, "win_levels", None),
            "available": list(getattr(fr, "available_actions", []) or []),
        }
        self.last = obs
        return obs

    def reset(self):
        """0 = RESET (kesin)."""
        return self._obs(self._env.reset())

    def press(self, n: int):
        """1,2,3,4,5,7 gibi basit tus. (6 icin click() kullan.)"""
        assert n != CLICK, "6 = CLICK: click(x,y) kullan"
        fr = self._env.step(GameAction[f"ACTION{n}"] if n != 0 else GameAction["RESET"])
        return self._obs(fr)

    def click(self, x: int, y: int):
        """6 = CLICK (kesin): (x,y)'ye tikla."""
        fr = self._env.step(GameAction["ACTION6"], {"x": int(x), "y": int(y)})
        return self._obs(fr)

    def act(self, action: int, x=None, y=None):
        """Genel giris: token uyumlu ([A0],[A6@x,y],[A1]...)."""
        if action == RESET:
            return self.reset()
        if action == CLICK:
            return self.click(x, y)
        return self.press(action)

    # --- ajanin o an bildikleri ---
    def what_i_know(self):
        """Su anki durumda gecerli aksiyonlar + haklarindaki bilgi/hipotez."""
        avail = self.last["available"] if self.last else []
        # RESET(0) her zaman kullanilabilir; digerleri available'a bagli.
        rows = []
        for a in [0, 6, 1, 2, 3, 4, 5, 7]:
            usable = (a == 0) or (a in avail)
            tag = self.learned.get(a) or describe(a)
            rows.append((a, usable, tag))
        return rows


if __name__ == "__main__":
    import sys
    game = sys.argv[1] if len(sys.argv) > 1 else "lf52"
    h = Hand(game)
    print(f"=== {game}: EL hazir ===")
    print(f"durum={h.last['state']}  seviye={h.last['levels_completed']}"
          f"/{h.last['win_levels']}  gecerli={h.last['available']}")
    print("\nAjanin aksiyonlar hakkinda BILDIKLERI:")
    for a, usable, tag in h.what_i_know():
        mark = "✓" if usable else "·"
        print(f"  [{mark}] A{a}: {tag}")
