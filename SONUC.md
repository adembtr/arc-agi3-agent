# SONUC.md — SMT kural öğrenme + CEGIS ölçümleri (solver_gorev.md şartnamesi)

> Tarih: 2026-07-25 · Tohumlar sabit (0,1) · z3-solver 5.0 · offline wheel: `AGI/solver_wheels/`

## 0. Ön koşul (§1) — ✅

- z3 ARC-AGI-3-Agents venv'ine kuruldu, şartname snippet'i doğrulandı.
- Offline wheel indirildi (`solver_wheels/z3_solver-5.0.0.0-...whl`), temiz venv'de
  `--no-index --find-links` ile offline kurulum TEST EDİLDİ, çalışıyor.

## 1. Yüklem havuzu (§2.2) — ✅

- `predicates.py`: **192 oyun-nötr yüklem** (aksiyon 8, küme-slot 32, renk 16,
  boyut 4, kenar 4, komşu-renk 64, komşu-boş 4, yalnızlık 2, sahne 41+,
  sahne-renk-durumu 21). Küme id'leri slot'lara ilk-görülme sırasıyla bağlanır
  (sabit vektör uzunluğu). vc33'te gözle doğrulandı (üst-kenar çizgisi →
  `at_border_top/left/right`, `neighbor_down_empty` doğru çıktı).

## 2. FAZ 1 — MaxSAT kural öğrenme (§2) — ✅ KABUL GEÇTİ

Kurulum: vc33, 1500 adım yenilik-keşfi (1472 satır), zamansal %80/%20 bölme.

**Kritik bulgu — tek VE-kuralı YETMEDİ:** şartnamenin saf hali (2.4) vc33'te
TÜM etkiler için `unseparable`. İki neden (ölçüldü):
1. **Ayrık yapı:** pozitifler ≥3 farklı odak-kümeye yayılıyor ("s1 VEYA s2'ye tıkla")
   → conjunctionların kesişimi J genel yüklemlere düşüyor, 972/972 negatif taşıyor.
2. **Gizli durum:** 160 satırda AYNI vektör hem pozitif hem negatif →
   bu havuz üzerinde HİÇBİR mantık ayıramaz.

Çözümler (AYAR.md'de gerekçeli): kural LİSTESİ (ardışık kapsama, her terim yine
Z3-minimal), polarite (çoğunluk-varsayılan), +21 oyun-nötr yüklem.

### FAZ 1 kabul tablosu (vc33, tutulan %20)

| E | Etki | Polarite | Doğruluk | Terim sayısı | En uzun terim | Süre |
|---|---|---|---|---|---|---|
| 2 | azaldı | E-OLMAZ | 0.973 | 6 | 4 | 0.12sn |
| 3 | büyüdü | E-OLMAZ | 0.953 | 6 | 4 | 0.12sn |
| 4 | oluştu | E-olur | 0.902 | 6 | 3 | 0.09sn |
| 5 | kayboldu | E-olur | 0.854 | 6 | 3 | 0.08sn |
| 7 | renk-değişti | E-olur | 0.841 | 6 | 3 | 0.08sn |
| 10 | GAMEOVER | E-olur | 0.983 | 6 | 3 | 0.13sn |

**KABUL: 6/6** (kriter: ≥0.80 doğruluk ✅, terim ≤5 yüklem ✅, <5sn ✅).
Örnek öğrenilen kural (GAMEOVER): `EĞER alone_in_row VE exists_cluster_s5`.

`unseparable` sayacı (tek-kural denemesi): 6/6 etki — yüklem havuzu değil,
kural FORMU yetersizdi; liste formu çözdü. Kalan gürültü (örn. E7: p100/n152
çakışan satır) vc33'ün gerçek gizli durumu — görünür karede olmayan bilgi.

## 3. FAZ 2 — CEGIS deney seçimi (§3) — ❌ KABUL GEÇEMEDİ

Mimari (`cegis.py`): `CegisAgent(WrongElimReward)` — çözücü üstte, yanlış-eleme
yedek (şartname §5). Karar sırası:
1. GÜVENLİK: GAMEOVER-kuralı ateşleyen adaylar veto (kapılı: ≥5 pozitif,
   ≥2 yüklemli terim, tıkanınca devre dışı)
2. ÖLÜ-HAMLE ATLAMA: "yapısal etki OLMAZ" tahminli adaylar atlanır
   (temel her ölü hamleyi deneyerek öğrenir; çözücü DENEMEDEN genelller)
3. SÖMÜRÜ: WIN-kuralı ateşleyen aday hemen oynanır
4. DENEY (CEGIS): R1/R2 ayrışan aday — SADECE boşta gezerken (`since_new≥2`)
   + seviye başına ≤8 deney (ablasyon: sınırsız deney sv2 kaybettirdi)
5. YEDEK: WrongElimReward (yanlış-eleme + Go-Explore)

Güvenlik: her Z3 çağrısı timeout'lu (2sn), toplam bütçe 120sn — aşılırsa çözücü
KAPANIR, saf yedek sürer (ajan asla donmaz). Determinizm: tohum sabit.

### Ara ablasyon bulguları (vc33, 600 adım)
- Kapısız deneyler: 16 deney → sv2 KAYBI (kritik anda hamle çaldı). Kapılı: sv2 geri geldi.
- Aşırı-genel GAMEOVER vetosu: yeni seviyenin şekillerinde yanlış ateşleyip
  doğru hamleyi engelledi → kapı eklendi.
- vc33'te ölü-hamle atlama İŞLEMEZ: her tıklama yapısal etki üretiyor (sayaç).
- Seviye-1-öncesi sömürü İMKANSIZ: ilk WIN örneği olmadan WIN kuralı yok.

### FAZ 2 kabul tablosu (şartname §8: seviye-1'e-kadar-aksiyon, 2000 adım, tohum 0/1)

| Oyun | Temel: aksiyon/sv1 | Çözücü: aksiyon/sv1 | Kazanç | Ulaşılan seviye | unseparable |
|---|---|---|---|---|---|
| vc33 | 277, 23 (ort 150) | 277, 23 (ort 150) | %0 | 2 = 2 | 15337 |
| tn36 | 99, 97 (ort 98) | 100, 97 (ort 98.5) | −%1 | 1 = 1 | 6352 |
| r11l | 411, 1202 (ort 806) | 864, 872 (ort 868) | −%8 | 1 = 1 | 3214 |
| cd82 | −, 1216 | −, − | **SEVİYE KAYBI** | 1 → 0 | 1922 |

**KABUL: GEÇEMEDİ** (kriter: ≥2 oyunda ≥%25 daha az aksiyon, seviye kaybı yok →
gerçek: 0/4 kazanç + cd82'de gerileme).

### Neden geçemedi (dürüst analiz)
1. **Seviye-1-öncesi sömürülecek şey yok:** WIN kuralı ilk seviye-atlamadan önce
   ÖĞRENİLEMEZ (pozitif örnek yok). Metrik tam da o pencereyi ölçüyor.
2. **Kurallar tanımlayıcı-doğru ama karar-değiştirici değil:** FAZ 1'in %84-98
   doğruluğu, temel yöntemin deneyerek zaten edindiği bilgiyi tahmin ediyor;
   temel-üstü BİLGİ katmıyor (aynı yörüngeler: 277/23 birebir aynı).
3. **cd82 gerilemesi:** ölü-hamle atlama nesne-satırlarından aşırı genelleyip
   doğru hamleleri de atladı (olu-atla=4489) → tek geçen tohumu kaybettirdi.
4. `unseparable` sütunu: binlerce tekil-kural başarısızlığı = etkiler tekil
   conjunction değil; kural-listesi zorunlu (FAZ 1 bulgusuyla tutarlı).

**Sonuç — şartname §9 kapısı: FAZ 3 (makro besteleme) İNŞA EDİLMEDİ.**
`plan.py` = kapı gerekçesi + ileride kurulacaksa tasarım notu.

## 4. EK DENEY — Bisimülasyon: 0.22 eşiği yerine davranışsal denklik

> "Bir şeyi adıyla değil, davranışıyla tanımla." Partition refinement:
> tek blokla başla; aynı bloktaki iki imza bir aksiyonda kanıtla farklı
> davranırsa böl. Eşik YOK, hiperparametre YOK. (`bisim.py`)
> İki çatışma tanımı: **hoşgörülü** = etki-kümeleri AYRIK ise farklı
> (gürültüye dayanıklı, kaba); **strict** = eşit değilse farklı (ince,
> determinizm-dışında aşırı-böler). Bu seçim sayısal eşik değil YAPISAL önsel.

### Küme sayıları (600 adım, aynı keşif izi)

| Oyun | İmza | Eşik(0.22) küme | Bisim-hoşgörülü blok | Bisim-strict blok |
|---|---|---|---|---|
| vc33 | 88 | 9 | 2 | 7 |
| tn36 | 38 | 9 | 1 | 5 |
| r11l | 92 | 31 | 2 | 17 |
| cd82 | 97 | 16 | 16 | 40 |

### Seviye testi (WrongElim, kümeleme değiştirildi; 2000 adım, tohum 0/1)

| Oyun | Eşik(0.22) sv1@ | Hoşgörülü sv1@ | Strict sv1@ | En iyi |
|---|---|---|---|---|
| vc33 | 277, 23 (ort 150) **sv2** | 99, 438 (ort 268) sv1 | 163, 219 (ort 191) sv1 | **eşik** (sv2'yi tek o gördü) |
| tn36 | 99, 97 (ort 98) | **30, 43 (ort 36) → %63 az** | 117, 366 (ort 241) | **hoşgörülü** |
| r11l | 411, 1202 (ort 806) | 350, 330 (ort 340) → %58 az | **17, 251 (ort 134) → %83 az** | **strict** |
| cd82 | −, 1216 (1/2 tohum) | −, − geçemedi | 1036, − (1/2 tohum) | ~berabere (farklı tohumlar) |

### Değerlendirme (dürüst)
- **Bisimülasyon 2 oyunda eşiği EZDİ** (tn36 %63, r11l %83'e varan daha az aksiyon):
  davranış blokları W-elemesini tüm eşdeğer şekillere ANINDA genelliyor —
  eşikli kümenin tek tek elemek zorunda kaldığını bir denemede eler.
- **vc33'te eşik kazandı:** seviye-2'yi sadece o gördü. Kaba davranış blokları
  vc33'ün görünüşte-farklı-davranışta-benzer düğmelerini erken birleştirip
  ayrımı kaybediyor (gizli-durumlu oyunda davranış imzası yanıltıcı).
- **Tek kip her yerde kazanmıyor:** hoşgörülü tn36'da, strict r11l'de en iyi.
  Hangi çatışma tanımının doğru olduğu OYUNUN determinizmine bağlı → sıradaki
  doğal adım: determinizm-testine göre kip seçen uyarlanır sürüm
  (deterministik oyun → strict, gizli-durumlu → hoşgörülü/eşik).
- Net kazanım: **elle ayarlanan 0.22 sayısal eşiğin kaldırılabilir olduğu
  KANITLANDI** — iki oyunda büyük kazançla. Ama evrensel üstünlük İSPATLANMADI;
  vc33 gerilemesi gerçek.

## 5. Birim testler

`test_solver.py`: **17/17 OK** — learn_rule (min/occam/unseparable/no-candidate),
learn_ruleset (ayrık yapı/çelişki-gürültü), second_rule (ikinci hipotez/ayrışan
girdi/unique), predicates (sabit uzunluk/slot kararlılığı), CegisAgent duman.

## 6. Büyük resim — bu görevden çıkan dersler

1. **FAZ 1 çalışıyor:** Z3/MaxSAT kural öğrenme hızlı (<0.2sn) ve doğru (0.84-0.98).
   Kural formu ders: oyun mekaniği tek conjunction DEĞİL; ayrık (kural listesi) +
   polarite şart. `unseparable` gerçekten en değerli teşhis sinyali çıktı
   (hem form eksiğini hem gizli durumu ayrı ayrı gösterdi).
2. **FAZ 2 çalışmıyor (bu haliyle):** doğru tahmin ≠ daha iyi karar. Deney seçimi
   ilk-seviye metriğinde yapısal olarak kazanamıyor; model-tabanlı kazanç
   seviye-içi-tekrar/seviye-2+ transferinde aranmalı.
3. **Bisimülasyon umut verici:** davranışsal denklik 2/4 oyunda çok büyük kazanç;
   uyarlanır kip + eşik-hibrit sıradaki en yüksek beklentili iş.
4. Kaggle notu: z3 offline wheel hazır; çözücü bütçe/timeout korumaları test edildi
   (bütçe aşımında kendini kapatıp yedeğe düşüyor — ajan hiç donmadı).

---

# EK — Hedef hipotezi + meta + şema görevi (hedef_gorev.md, 2026-07-25)

> Tam ölçümler: `denme/goal/SONUC2.md`. FAZ 2'nin "seviye-1-öncesi sömürülecek şey
> yok" teşhisine yanıt: insan hedefi DENEYEREK değil, ilk kareden GEOMETRİYLE kuruyor.

## A) Hedef hipotezi (goals.py) — ✅ 4/4 (aksiyonsuz, ilk kare)
5 oyun-nötr geometrik şablon (UNIFY/FIT/OVERLAP/CONSISTENT/COLLECT). İlk karede,
aksiyon harcamadan, insan hedefiyle eşleşen hipotez ilk 2 sırada:
m0r0→UNIFY, g50t→FIT, ar25→OVERLAP, lf52→COLLECT. **Notun asıl tezi kanıtlandı:
dünya bilgisi olmadan, saf sayıyla (şekil imzası, tümleyenlik, frekans) hedef kuruldu.**

## B) Meta tespit (meta.py) — ✅ 4/4
ft09 sayaç, m0r0 sayaç, g50t A5-tehlike (0.70 geri-sarma vs 0.23), ar25 coupled.
Hepsi sayım/geometri; A0=evrensel-RESET dışlanır; tehlike ≥2 gözlem kapılı.

## C) Şema/φ (schema.py) — çekirdek ✅, transfer ⚠️ ölçülemedi
CONSISTENT tespiti + φ çıkarımı ft09'da **φ={0→8, 2→9}** buldu = insan notundaki
eşlemeyle BİREBİR, aksiyonsuz. AMA ft09 sv1 geçilemediği için sv2-transfer ölçülemedi.

## D) Entegrasyon (goal_agent.py) — ❌ 0/5 yeni oyunda sv1
Hedef+meta+progress-tepe-tırmanışı+makro+yedek. **Yeni oyunlardan seviye: 0/5.**
Sert gerileme yok (tn36/r11l/cd82 sv1 korundu; vc33 sv2→sv1 tohum-bağımlı).

**Kesin ders:** darboğaz artık "hedefi bilmemek" DEĞİL (A/B/C-çekirdek çalışıyor) —
darboğaz saf **PLANLAMA**: öğrenilen kural (FAZ 1) + hedef (bu görev) üstünde gerçek
çok-adımlı arama (BFS/A*/SAT-plan). Model-free progress-tırmanışı makro duvarını
kıramıyor (ar25: OVERLAP progress 0.10'da plato). Girdiler hazır; eksik olan planlayıcı.
