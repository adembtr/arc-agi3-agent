#!/usr/bin/env python3
"""VSA — Vektor Sembolik Mimari (hiperboyutlu hesaplama).

Her BILGI bir vektor. Kucuk bilgiler BAGLANIP (bind) HARMANLANIP (bundle) daha
buyuk bilgiler olusur. En kokte atom (piksel/sekil/aksiyon), en tepede tum durum/kural.

MAP modeli (Multiply-Add-Permute), bipolar {-1,+1}, D boyut:
  - bind(a,b)   = a * b        (eleman-eleman carpim; rol<->deger esle; kendi-tersi)
  - bundle(...) = sign(Σ)      (toplama; kume/yapi; hepsine benzer, ayirt edilebilir)
  - unbind(x,r) = x * r        (bind kendi-tersi oldugu icin ayni islem)
  - permute(a)  = roll(a,1)    (sira/dizi/hiyerarsi)
  - sim(a,b)    = <a,b>/D      (kosinus benzeri; -1..+1)

Metin YOK, gradyan YOK, LLM YOK. Tek-atista kural yazilir, cebirle kullanilir.
"""
import numpy as np

D = 10000                      # hiperboyut (yuksek -> atomlar neredeyse dik)
_RNG = np.random.default_rng(12345)


def rand_hv(rng=None):
    r = rng if rng is not None else _RNG
    return r.integers(0, 2, size=D, dtype=np.int8) * 2 - 1   # {-1,+1}


def bind(a, b):
    return (a * b).astype(np.int8)


def unbind(x, r):
    return (x * r).astype(np.int8)                            # bipolar: bind = kendi tersi


def bundle(vectors):
    """Coklu vektoru TEK vektorde topla (kume/yapi). sign(Σ), sifir->+1."""
    s = np.sum(np.stack(vectors).astype(np.int32), axis=0)
    out = np.where(s >= 0, 1, -1).astype(np.int8)
    return out


def bundle_weighted(pairs):
    """[(vec,agirlik)] -> agirlikli harman (sik gorulen bilgi baskin)."""
    s = np.zeros(D, dtype=np.float64)
    for v, w in pairs:
        s += v.astype(np.float64) * w
    return np.where(s >= 0, 1, -1).astype(np.int8)


def permute(a, k=1):
    return np.roll(a, k).astype(np.int8)


def sim(a, b):
    return float(np.dot(a.astype(np.int32), b.astype(np.int32))) / D


# ---------------------------------------------------------------------------
# TEMIZLEME HAFIZASI — gurultulu vektoru en yakin BILINEN atoma esler.
# (unbind sonrasi cikan yaklasik vektoru "temiz" atoma cevirir.)
# ---------------------------------------------------------------------------
class ItemMemory:
    def __init__(self):
        self.names = []
        self.mat = None            # (n, D)
        self._rng = np.random.default_rng(777)

    def get(self, name):
        """Isimli atom. Yoksa YENI rastgele vektor uret (yeni kavram = yeni vektor)."""
        if name in self.names:
            return self.mat[self.names.index(name)]
        v = rand_hv(self._rng)
        self.names.append(name)
        self.mat = v[None, :] if self.mat is None else np.vstack([self.mat, v])
        return v

    def cleanup(self, vec, topk=1):
        """En benzer bilinen atom(lar) -> [(isim, benzerlik)]."""
        if self.mat is None:
            return []
        sims = (self.mat.astype(np.int32) @ vec.astype(np.int32)) / D
        idx = np.argsort(-sims)[:topk]
        return [(self.names[i], float(sims[i])) for i in idx]


if __name__ == "__main__":
    print(f"VSA D={D}")
    mem = ItemMemory()
    # 1) atomlar neredeyse DIK (rastgele yuksek-boyut)
    a, b = mem.get("A"), mem.get("B")
    print("1) atom benzerligi A·B =", round(sim(a, b), 3), "(≈0 bekleniyor)")
    # 2) bind + unbind -> filler geri gelir
    rol, deger = mem.get("RENK"), mem.get("KIRMIZI")
    x = bind(rol, deger)
    geri = unbind(x, rol)
    print("2) unbind(bind(RENK,KIRMIZI),RENK) ≈ KIRMIZI? sim =",
          round(sim(geri, deger), 3), "->", mem.cleanup(geri))
    # 3) bundle -> kume uyeligi
    s = bundle([mem.get("X"), mem.get("Y"), mem.get("Z")])
    print("3) bundle{X,Y,Z} icinde X var mi? sim =", round(sim(s, mem.get("X")), 3),
          "| W var mi? sim =", round(sim(s, mem.get("W")), 3))
