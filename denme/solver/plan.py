#!/usr/bin/env python3
"""FAZ 3 — Makro besteleme (BFS / SAT-planlama).

*** KAPI: INSA EDILMEDI — sartname §4/§9 geregi. ***

Sartname acik: "FAZ 3'e sadece FAZ 1 + FAZ 2 IKISI DE gecerse basla.
Bes sey birden insa etme — hangi katmanin ise yaradigini olcemezsen
korlemesine ilerlemis olursun."

Olcum sonuclari (SONUC.md):
  FAZ 1 (MaxSAT kural ogrenme): KABUL GECTI (6/6 etki, dogruluk 0.84-0.98)
  FAZ 2 (CEGIS deney secimi):   KABUL GECEMEDI (0/4 oyunda kazanc,
                                cd82'de seviye kaybi 1->0)

FAZ 2'nin gecememe NEDENI (olculdu, SONUC.md §4):
  - Seviye-1 oncesi somuru IMKANSIZ: ilk WIN ornegi olmadan WIN kurali yok.
  - Ogrenilen kurallar tanimlayici dogru (FAZ 1) ama karar-degistirici degil:
    yanlis-eleme temeli ayni bilgiyi deneyerek zaten ediniyordu.
  - cd82: olu-hamle atlama asiri genelleyip dogru hamleleri de atladi.

Kurallar uzerinde BFS'in on kosulu, kurallarin AKSIYON-SECICI olmasi; once
FAZ 2 katmaninin kazanc urettigi kanitlanmali. O kanit gelmeden buraya makro
katmani dikmek, olcusuz uçdan-uca karmasiklik eklemek olur.

Gelecekte insa edilecegi zaman plan (sartname §4):
  1. Once basit: ogrenilen kurallar uzerinde derinlik 3-4 BFS
     (durum = nesne-duzeyi soyutlama, HAM 64x64 grid DEGIL).
  2. BFS yetmezse SAT-planlama (Kautz & Selman): zaman-adimli aksiyon
     degiskenleri + kurallar gecis aksiyomu + frame aksiyomu; k=1'den
     sat cikana kadar artir.
"""

if __name__ == "__main__":
    print(__doc__)
