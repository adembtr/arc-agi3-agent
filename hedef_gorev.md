# GÖREV: Hedef hipotezi + meta-nesne tespiti + seviye şeması (ARC-AGI-3)

> Uygulama şartnamesi. Proje kökü: `/home/adem/Desktop/AGI/`
> Yeni kodlar: `denme/goal/` altına. **Mevcut hiçbir dosyayı bozma.**
> Ön okuma: `denme/solver/SONUC.md` (FAZ 2 neden geçemedi), `plan.md` §15–§17.

---

## 0. NEDEN BU GÖREV

`SONUC.md` §3'te ölçülmüş kesin bulgu:

> *"Seviye-1-öncesi sömürülecek şey yok: WIN kuralı ilk seviye-atlamadan önce
> ÖĞRENİLEMEZ (pozitif örnek yok)."*

Bu doğru teşhis ama eksik. Çünkü **insan bu sorunu yaşamıyor.** İnsan oyun izlerine
bakıldığında (`player/notes/*.txt`), oyuncu hedefi **hiç aksiyon yapmadan, ilk karede,
sadece geometriden** kuruyor.

Örnekler, birebir insan notlarından:

| Oyun | İlk karede kurulan hedef | Dayanak |
|---|---|---|
| m0r0 | "mavi 10'ları birleştireceğim" | iki özdeş şekil ayrı duruyor |
| g50t | "mavi 9'u diğer mavi 9'un içine koyacağım" | iki şekil iç içe geçince tam kare oluyor |
| ar25 | "sağdaki şekli sarı şeklin üzerine getireceğim" | aynı yönelim + hizalı |
| ft09 | "ortadaki kare etraftakileri temsil ediyor" | küçük desen ↔ büyük dizilim eşleşmesi |
| lf52 | "aynı yeşilleri birleştireceğim" | aynı renkli şeyler ayrı duruyor |

**Hiçbirinde ödül sinyali yok. Hepsi ilk karenin geometrisinden.**

Bu görevin amacı: bunu mekanikleştirmek. Ajan seviye 1'i geçmeden önce bir hedef
hipotezine sahip olacak, böylece planlayıcının hedefi olacak ve CEGIS'in ölçüleceği
bir pencere doğacak.

**Kritik not:** insan notlarının hiçbirinde dünya bilgisi yok. "Elma", "araba", "kapı"
geçmiyor. "Siyah 5 arka plan çünkü çoğunluk" → aritmetik. "İç içe geçince kare oluyor"
→ geometri. Hepsi sayıdan hesaplanabilir. Bu görevde de öyle olacak.

---

## 1. MODÜL A — `denme/goal/goals.py` (öncelik 1)

### 1.1 Ne yapar

İlk kareyi (veya herhangi bir kareyi) alır, nesne kümesi üzerinden **hedef şablonlarını**
puanlar, sıralı hipotez listesi döndürür. Aksiyon gerektirmez.

### 1.2 Hedef şablonları (hepsi oyun-nötr, geometrik)

Her şablon `(ad, hedef_yüklemi, puan, ilgili_nesneler)` döndürür.

**T1 — `UNIFY(A,B)`** — iki eşdeğer nesne ayrı duruyor, birleştirilmeli
- Tespit: `sig(A) == sig(B)` (normalize şekil imzası eşit), `A ≠ B`, aralarında mesafe > 0
- Hedef yüklemi: `E_MERGE` olayı, veya `centroid_dist(A,B) == 0`
- Puan: eşdeğer çift sayısı ters orantılı (tek çift varsa güçlü sinyal), mesafe ile artan
- Kanıt: m0r0, lf52

**T2 — `FIT(A,B)`** — iki nesne tamamlayıcı, iç içe geçmeli
- Tespit: `A` ve `B`'nin sınırlayıcı kutuları benzer boyutta VE
  `dolu(A) ∩ dolu(B_kaydırılmış) = ∅` olacak bir kaydırma var VE
  `dolu(A) ∪ dolu(B_kaydırılmış)` dolu bir dikdörtgen
- Hedef yüklemi: o kaydırmanın gerçekleşmesi
- Puan: birleşimin dikdörtgene doluluk oranı
- Kanıt: g50t ("iç içe girdiğinde tam bir kare oluşuyor")

**T3 — `OVERLAP(A,B)`** — aynı şekil farklı yerde, üst üste getirilmeli
- Tespit: `norm_mask(A) == norm_mask(B)` (renk farklı olabilir), konum farklı
- Hedef yüklemi: `centroid(A) == centroid(B)`
- Puan: şekil eşleşmesinin kesinliği; aynı yönelimdeyse artır (ayna ise azalt)
- Kanıt: ar25 ("aynı yönde ve tam üst üste oturuyor")

**T4 — `CONSISTENT(S,L)`** — küçük desen büyük dizilimin haritası
- Tespit: `S` küçük bir nesne, hücre sayısı `n`; `L` = `n` adet nesnenin uzamsal dizilimi;
  `S`'nin hücre düzeni ile `L`'nin nesne düzeni izomorf (aynı satır/sütun yapısı)
- Hedef yüklemi: bir renk bijeksiyonu `φ` altında `renk(S[i]) = φ(renk(L[i]))` her `i` için
- **`φ` BİLİNMEZ, öğrenilecek.** Başlangıçta kimlik varsayılır; ters düşerse ters çevrilir.
- Puan: izomorfizmin kesinliği
- Kanıt: ft09 — ve dikkat: insan 3 seviyede de `φ`'yi yeniden türetmek zorunda kaldı,
  şema aynı kaldı. Bu §3'ün gerekçesi.

**T5 — `COLLECT(A*)`** — çok sayıda küçük eşdeğer nesne, sayıları azalmalı
- Tespit: ≥3 adet aynı imzalı küçük nesne
- Hedef yüklemi: `count(sig) < başlangıç`
- Puan: nesne sayısıyla artan
- Kanıt: lf52 (yeşilleri toplama), genel örüntü

### 1.3 Arayüz

```python
def hypothesize_goals(objects, grid) -> list[GoalHypothesis]:
    """Puana göre azalan sıralı hipotez listesi. Aksiyon YAPMAZ."""

class GoalHypothesis:
    name: str                  # "UNIFY", "FIT", ...
    predicate: Callable        # (objects, grid) -> bool  : hedef sağlandı mı
    progress: Callable         # (objects, grid) -> float : 0..1 ne kadar yakın
    objects: list              # ilgili nesneler
    score: float               # ilk plausibility
    alive: bool = True
```

`progress` fonksiyonu kritik: planlayıcı bunu A* sezgiseli olarak kullanacak.
`UNIFY` için `progress = 1 - normalize(mesafe)`. `FIT` için örtüşme oranı. vs.

### 1.4 Hipotez elemesi (CEGIS mantığı, hedef üzerinde)

```
1. En yüksek puanlı hipotezi AL, plana ver
2. Hipotezin progress'i N adım boyunca artmıyorsa → alive=False, sonrakine geç
3. Seviye atlama olduğunda hangi hipotez aktifse → puanını KALICI artır
4. Seviye atlamadan game-over → aktif hipotezin puanını düşür
```

Bu, hedefin de öğrenilmesini sağlar; sabit kodlanmış hedef yok.

### 1.5 Kabul kriteri (MODÜL A)

`m0r0`, `g50t`, `ar25`, `lf52` üzerinde — **bunlar şu an GEÇİLEMEYEN oyunlar**:

- İlk karede üretilen en yüksek puanlı hipotez, insan notundaki hedefle **eşleşmeli**
- Eşleşme tablosu: m0r0→UNIFY, g50t→FIT, ar25→OVERLAP, lf52→UNIFY veya COLLECT
- **Geçer: 4/4'te doğru hipotez ilk 2 sırada.**

Bu ölçümü aksiyon harcamadan yapabilirsin. Önce bunu koştur, raporla, dur.

---

## 2. MODÜL B — `denme/goal/meta.py` (öncelik 2)

İnsan notlarında tekrar eden, hedef OLMAYAN ama kritik üç nesne tipi var.
Bunlar hedef adaylarından **dışlanmalı**, yoksa planlayıcıyı yanıltır.

### 2.1 Sayaç tespiti
- İnsan notu (ft09): *"bu düz satır oyunun aksiyon adet sayısı oluyor"*
- İnsan notu (m0r0): *"Siyah 5 çizgileri oyunun kaç klik sonra biteceğini söylüyormuş"*
- **Tespit:** bir nesne/satır, **hangi aksiyon yapılırsa yapılsın** her adımda aynı yönde
  monoton değişiyorsa → `meta:counter`
- Kullanım: hedef adayı OLAMAZ; kalan bütçe sinyali olarak kullan

### 2.2 Tehlike tespiti
- İnsan notu (g50t): *"A5 tuşu oyunu sıfırlıyormuş"*
- İnsan notu (m0r0): *"Turuncu 8'in olduğu yerlere değdiği anda hemen oyun sıfırlanıyor"*
- **Tespit:** bir aksiyon veya bir temas, `E_BACK`(9) üretiyorsa veya daha önce görülmüş
  erken bir duruma dönüyorsa → `hazard`
- İki tip ayır: **aksiyon-tehlikesi** (A5 gibi) ve **temas-tehlikesi** (belirli imzaya değme)
- Kullanım: planlayıcıda veto. Ama **kapılı**: ≥2 gözlem şart (SONUC.md'deki aşırı-genel
  veto hatası tekrarlanmasın)

### 2.3 Bağlaşık kontrol tespiti
- İnsan notu (ar25): *"bu tuş şekli yukarı götürdü hemde sütünün sol ve sağında olan
  iki şekli aynı anda"*
- İnsan notu (m0r0): *"Birini siyah beşin bittiği yerde duvara denk getirip gitmesini
  engelliyoruz"* ← **çözümün anahtarı bu**
- **Tespit:** bir aksiyon ≥2 nesneyi **aynı yer değiştirmeyle** hareket ettiriyorsa
  → o nesneler `coupled`
- **Planlama ipucu (çok önemli):** bağlaşık nesneleri ayırmanın tek yolu birini engele
  dayamaktır. Planlayıcı `coupled` gördüğünde "önce A'yı duvara sür, sonra B'yi hareket
  ettir" makrosunu aday listesine eklemeli.

### 2.4 Arka plan
- İnsan notu (ft09): *"siyah 5 diye bir arka plan var ve bu çoğunluk olduğu için"*
- **Tespit:** en yüksek frekanslı hücre değeri. Zaten `RoleModel`'de var, `goals.py`'ye taşı.

### 2.5 Kabul kriteri (MODÜL B)

| Oyun | Beklenen tespit |
|---|---|
| ft09 | alt satır → `meta:counter` |
| m0r0 | üst/alt siyah-5 çizgileri → `meta:counter`; turuncu-8 teması → `hazard` |
| g50t | A5 → `hazard:action` |
| ar25 | A1/A2/A3 → iki şekil `coupled` |

**Geçer: 4/4 oyunda beklenen tespit çıkıyor, yanlış-pozitif yok.**

---

## 3. MODÜL C — `denme/goal/schema.py` (öncelik 3)

### 3.1 Gözlemlenen olgu

İnsan notlarında en net örüntü bu. ft09'da:

- **Seviye 1:** merkez kare ↔ çevre dizilimi. `beyaz-0 → turuncu-8`, `gri-2 → mavi-9`
- **Seviye 2:** aynı şema, ama eşleme TERS. İnsan: *"bu böyle olmaması gerekiyormuş...
  renkleri değiştireceğim"* → 1 seviye kaybı
- **Seviye 3:** aynı şema, eşleme yine farklı, üstelik özyinelemeli

Kullanıcının kendi tespiti: *"tek zorluk yeni engelleri tanımlamak, hedefi belirlemem
1-2 seviyemi yedi."*

### 3.2 Ayrım — kodun temel kararı

```
ŞEMA    (seviyeler arası TAŞINIR):
  - hedef şablonu kimliği (UNIFY / FIT / OVERLAP / CONSISTENT / COLLECT)
  - aksiyon semantiği (A2 = aşağı, A6 = tıkla-seç)
  - tehlike aksiyonları (A5 = reset)
  - bağlaşıklık yapısı
  - makro kalıpları ("duvara daya sonra ayrıştır")

BAĞLAMA (her seviyede SIFIRLANIR):
  - küme id ↔ rol eşlemesi
  - renk ↔ anlam eşlemesi (φ)
  - hangi somut nesne hedef, hangisi engel
  - konum bilgisi
```

### 3.3 Seviye geçişinde davranış

```python
def on_level_up(state):
    schema.keep()          # şablon, aksiyon semantiği, tehlike, bağlaşıklık
    binding.reset()        # küme→rol, renk→anlam, nesne kimlikleri
    binding.rederive(first_frame_of_new_level)
```

**Yeniden türetme, sıfırdan öğrenme DEĞİL.** Şema `CONSISTENT` diyorsa, sadece `φ`
bijeksiyonunu yeniden çöz — bu küçük bir arama (renk sayısı kadar). İnsanın 1 seviye
kaybettiği yer tam burası; makine bunu bir kaç denemede yapmalı.

### 3.4 φ (eşleme) yeniden türetme — CONSISTENT için

```
1. Mevcut φ ile devam et (önceki seviyeden)
2. K adım içinde progress artmadıysa → φ'yi ters çevir
3. Hâlâ yoksa → küçük bijeksiyon araması (renkler arası permütasyon, MDL sıralı)
```

### 3.5 Kabul kriteri (MODÜL C)

`ft09` üzerinde: seviye 1 geçildikten sonra **seviye 2'ye harcanan aksiyon sayısı**,
seviye 1'e harcanandan **az** olmalı. Şema taşınıyorsa bu zorunlu bir sonuçtur.
Tersi çıkarsa şema taşınmıyor demektir.

---

## 4. ENTEGRASYON

```
ilk kare      → goals.hypothesize_goals()      → hedef hipotezi (aksiyon harcamadan)
              → meta.detect()                  → sayaç/tehlike/bağlaşık
her adım      → planner: progress'i artıran aksiyonu ara (A*, sezgisel = progress)
              → hazard vetosu (kapılı)
              → coupled görülürse "duvara daya" makrosu adaylara eklensin
hipotez ölü   → sıradaki hipoteze geç
seviye atlama → schema.keep() + binding.reset()
tıkanma       → WrongElimReward yedeği (mevcut)
```

Mevcut `solver/` katmanı korunur: geçiş kuralları oradan gelir, planlayıcı onların
üstünde arar. Bu görev **hedefi** ekliyor; kural öğrenme zaten çalışıyor (FAZ 1: 0.84–0.98).

---

## 5. NİHAİ KABUL

Ölçüm: `m0r0`, `g50t`, `ar25`, `lf52`, `ft09` (şu an **hiçbiri geçilemiyor**),
2000 adım, tohum 0/1.

| Kriter | Eşik |
|---|---|
| Hedef hipotezi doğruluğu (Modül A) | 4/4 oyunda ilk 2 sırada |
| Meta tespit (Modül B) | 4/4, yanlış-pozitif yok |
| **Seviye geçme** | **≥1 yeni oyunda seviye 1** |
| ft09 seviye-2 aksiyonu < seviye-1 aksiyonu | şema taşınıyor |
| Gerileme yok | vc33/tn36/r11l/cd82 seviyeleri korunuyor |

Bunlardan **"≥1 yeni oyunda seviye 1"** asıl testtir. Diğerleri teşhis.

---

## 6. YAPILMAYACAKLAR

- **Oyuna özel hiçbir sabit yazma.** `if game == "m0r0"` yasak. Şablonlar geometrik
  olmalı, oyun adı geçmemeli.
- **İnsan notundaki renkleri koda gömme.** Not "turuncu 8 tehlikeli" diyor; kod
  "E_BACK üreten temas tehlikelidir" demeli. Not spec'tir, sabit değil.
- **Beş modülü birden inşa etme.** Modül A → ölç → dur. Sonra B. Sonra C.
- Yeni eşik/hiperparametre eklersen `AYAR.md`'ye gerekçesiyle yaz.
- LLM çağrısı yok.

---

## 7. SIRA

1. `goals.py` yaz → §1.5 kabulünü ölç (aksiyon harcamadan) → **dur, raporla**
2. `meta.py` yaz → §2.5 kabulünü ölç → **dur, raporla**
3. Planlayıcıya bağla → nihai kabulü ölç → **dur, raporla**
4. `schema.py` yaz → §3.5 kabulünü ölç

`SONUC2.md`'ye her modülün ölçümünü ayrı yaz. Hangi modülün ne kattığını ayırt
edemezsen tekrar körlemesine ilerlemiş olursun.
