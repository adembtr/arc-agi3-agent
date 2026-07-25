#!/usr/bin/env python3
"""HIYERARSIK BILGI — kullanicinin vizyonu:
  piksel -> sekil -> nesne -> sahne -> KURAL -> en buyuk bilgi.
Her seviye, alt seviyelerin bind+bundle'i. Her sey TEK vektor. Metin/LLM/gradyan YOK.

Onemli: model "yesil" bilmiyor. "Bu ROL'de bu SEKIL, su ILISKI" biliyor. Kurali
tek-atista ogrenir (ONCE->SONRA bind) ve cebirle KULLANIR (tahmin).
"""
import numpy as np
import vsa


class Knowledge:
    def __init__(self):
        self.mem = vsa.ItemMemory()
        # sabit ROL vektorleri (yapinin "yuvalari")
        self.R = {r: self.mem.get(f"ROL_{r}") for r in
                  ["sekil", "renk", "konum_r", "konum_c", "rol", "once", "sonra",
                   "aksiyon", "iliski", "a", "b", "sonuc"]}
        self.rules = {}          # aksiyon -> tek-atis kural vektoru (ONCE->SONRA)

    # --- SEVIYE 1: sekil atomu (kok token) ---
    def shape(self, token):
        return self.mem.get(f"SEKIL_{token}")

    def color(self, c):
        return self.mem.get(f"RENK_{c}")

    def coord(self, val, axis):
        # konumu kaba kovaya bagla (yakin konumlar benzer degil — ayrik atom)
        return self.mem.get(f"KONUM_{axis}_{val // 6}")

    # --- SEVIYE 2: NESNE = sekil+renk+konum bind-bundle -> tek vektor ---
    def obj(self, token, color, r, c):
        return vsa.bundle([
            vsa.bind(self.R["sekil"], self.shape(token)),
            vsa.bind(self.R["renk"], self.color(color)),
            vsa.bind(self.R["konum_r"], self.coord(r, "r")),
            vsa.bind(self.R["konum_c"], self.coord(c, "c")),
        ])

    # --- SEVIYE 3: SAHNE = tum nesnelerin harmani (sirali permute ile) ---
    def scene(self, objs):
        if not objs:
            return self.mem.get("BOS_SAHNE")
        return vsa.bundle([vsa.permute(o, i) for i, o in enumerate(objs)])

    # --- SEVIYE 4: ILISKI = iki nesne + iliski-turu -> tek vektor ---
    def relation(self, oa, ob, rel_name):
        return vsa.bundle([
            vsa.bind(self.R["a"], oa),
            vsa.bind(self.R["b"], ob),
            vsa.bind(self.R["iliski"], self.mem.get(f"ILISKI_{rel_name}")),
        ])

    # --- SEVIYE 5: KURAL = (aksiyon,ONCE) -> SONRA. TEK-ATISTA ogren. ---
    def learn_rule(self, action, before_vec, after_vec):
        """Kurali bagla: bu aksiyon+once durumunda -> su sonra durumu.
        Ayni aksiyonun kurallarini bundle ile birik (cok ornek -> saglamlasir)."""
        pair = vsa.bind(vsa.bind(self.R["aksiyon"], self.mem.get(f"A_{action}")),
                        vsa.bind(self.R["once"], before_vec))
        rule = vsa.bind(pair, after_vec)          # (aksiyon,once) -> sonra
        if action in self.rules:
            self.rules[action] = vsa.bundle([self.rules[action], rule])
        else:
            self.rules[action] = rule

    def predict_after(self, action, before_vec):
        """Kurali KULLAN: bu aksiyon+once -> tahmini SONRA (cebirle cozulur)."""
        if action not in self.rules:
            return None
        pair = vsa.bind(vsa.bind(self.R["aksiyon"], self.mem.get(f"A_{action}")),
                        vsa.bind(self.R["once"], before_vec))
        return vsa.unbind(self.rules[action], pair)   # ≈ SONRA vektoru


# ===========================================================================
# TEST — hiyerarsi + tek-atis kural ogren+kullan
# ===========================================================================
if __name__ == "__main__":
    K = Knowledge()
    print("=== HIYERARSIK BILGI TESTI ===")

    # SEVIYE 2: ayni sekil farkli renk -> nesneler
    yesil1 = K.obj("kare", color=14, r=10, c=10)
    yesil2 = K.obj("kare", color=14, r=10, c=16)
    mavi = K.obj("kare", color=9, r=30, c=30)
    print("1) ayni sekil+renk farkli konum (yesil1 vs yesil2) sim =",
          round(vsa.sim(yesil1, yesil2), 3), "(orta: sekil/renk ayni, konum farkli)")
    print("   ayni sekil FARKLI renk (yesil1 vs mavi) sim =",
          round(vsa.sim(yesil1, mavi), 3))

    # nesneden SEKIL geri okunabilir mi (renk bilmeden sekli sorgula)
    geri_sekil = vsa.unbind(yesil1, K.R["sekil"])
    print("2) yesil1'den SEKIL cikar -> en yakin:",
          K.mem.cleanup(geri_sekil, 2))

    # SEVIYE 5: KURAL tek-atista ogren -> "iki yanyana kare -> tek kare"
    # ONCE = iki nesne yan yana (iliski), SONRA = tek nesne
    once = K.relation(yesil1, yesil2, "yanyana")
    sonuc_obj = K.obj("kare", color=14, r=10, c=13)   # ortada tek yesil
    K.learn_rule("A6", once, sonuc_obj)
    print("3) KURAL tek-atista ogrenildi: (A6, iki-yanyana-kare) -> tek-kare")

    # KURALI KULLAN: ayni durumu tekrar gorunce SONRA'yi tahmin et
    tahmin = K.predict_after("A6", once)
    print("   tahmin(A6, once) sonuc_obj'e benziyor mu? sim =",
          round(vsa.sim(tahmin, sonuc_obj), 3), "(yuksek = kural calisti)")
    # yanlis aksiyon icin tahmin dusuk olmali
    print("   ayni once ama ONCE vektoru bozulursa sim =",
          round(vsa.sim(tahmin, mavi), 3), "(dusuk = ayirt ediyor)")

    # GENELLEME: ayni yapida FARKLI RENK (iki mavi yanyana) -> ayni kural tahmini
    mavi1 = K.obj("kare", color=9, r=40, c=40)
    mavi2 = K.obj("kare", color=9, r=40, c=46)
    once_mavi = K.relation(mavi1, mavi2, "yanyana")
    tahmin_mavi = K.predict_after("A6", once_mavi)
    hedef_mavi = K.obj("kare", color=9, r=40, c=43)
    print("4) GENELLEME: iki MAVI yanyana -> tahmin, tek-mavi'ye sim =",
          round(vsa.sim(tahmin_mavi, hedef_mavi), 3),
          "(renk kurala girmediyse yapisal genelleme olur)")
