# ARC-AGI-3 — Proje Planı (mantık-tabanlı ajan)

> Amaç: Yarışmayı kazanmak. Yaklaşım: **kural + arama (program sentezi)**, ağırlık değil.
> Felsefe: Modelin "zekası" = veriden ezber (ağırlık) ya da kör hamle arama (BFS) DEĞİL;
> **oyunun mantığını kanıttan deşifre edip kurmak.** Bunu bir kere iyi kurarsak,
> hiç görülmemiş oyunları da çözer.
>
> **DURUM (2026-07-25):** İlk seviye-geçen yöntem bulundu. **Yanlış-eleme + ödül**
> (kullanıcının fikri) 4/25 oyunda seviye geçti (vc33 sv2; cd82, tn36, r11l sv1).
> VSA/TPR beyni (tek-atış kural) kuruldu ve doğrulandı, 2/4 kıyas oyununu geçti.
> Detay: **§14–§17.** Sıradaki darboğaz: uzun-dizi (makro) oyunları.

---

## 0. Nihai vizyon (kullanıcının kendi sözü)

- "Önce kendim gibi bir model, sonra kendimden daha zeki bir model."
- Yani: önce insanın (senin) oyunu anlama sürecini birebir mekanize et; sonra o süreci
  senden daha verimli yapan bir sürüm.
- En uç hedef: **DSL'in ilkellerini bile kendisi üreten** bir sistem → insanın hiç
  görmediği/duymadığı kavramları da çözebilen ajan (kütüphane öğrenme / DreamCoder mantığı).

### Strateji (pragmatik sıra)

1. **Kazanmak için BİRAZ atom ver** (oyun-nötr çekirdek). Kütüphane öğrenme bunlardan yenilerini
   kendi kursun. Amaç: önce yarışmayı al.
2. **%100'ü elde edince** en dip atoma (Turing-tam taban, "sıfırdan") in — genellik için.
3. **Değişmez kısıt:** yeni atom kurmak ASLA uzun sürmemeli. Atom kurmak = arama değil,
   sıkıştırma (bkz. §6.2). Çözme pahalı; atom kurma ucuz ve geleceği hızlandıran yatırım.

---

## 1. Yarışma gerçekleri (ARC-AGI-3)

- **Interaktif oyunlar.** Statik bulmaca değil; ajan gözlemler → aksiyon yapar → yeni gözlem.
- **Gözlem = 64×64 tamsayı grid** (değerler 0–15). Foto piksel DEĞİL, **sembolik** — yani
  nesne çıkarmak (bağlı bileşen) kolay ve kesin. Bu bizim en büyük avantajımız.
- **Aksiyonlar:** RESET(0) evrensel/sabit; ACTION6 her zaman "(x,y)'ye tıkla" (karmaşık aksiyon);
  ACTION1-5,7 basit tuşlar. **Aksiyonun ANLAMI oyuna özel** (ACTION1 = yukarı garantisi YOK).
  Her durumda `available_actions` geçerli aksiyonları verir.
- **Frame = grid DİZİSİ** (bir aksiyonun animasyonu). Son grid = nihai durum. Ara kareler
  bedava hareket bilgisi (dünya modeli için değerli).
- **Test oyunları GİZLİ ve YENİ.** Bizim çözdüğümüz oyunlar testte çıkmaz → çözümleri
  "eğitim verisi" olarak toplamak ANLAMSIZ. Amaç, oyunlar arası tekrar eden **mekanik
  sözlüğünü** çıkarmak.
- **Skor:** oyun başına ortalama; WIN vs GAME_OVER; az aksiyon = yüksek puan
  (= beceri kazanma verimi).
- **Kaggle:** notebook, ≤9 saat, internet YOK, offline wheel'ler, gizli oyunlar yerel
  "gateway" sunucusuyla sunulur, submission otomatik üretilir.
- **Ödül yolları (%100 olmadan da):** Milestone 2 (~$37.5K, 30 Eyl 2026),
  Final Leaderboard ($75K ilk-5, 2 Kas), Paper Track. %100/$700K hâlâ boşta.
- **Referans:** Milestone-1 galibi "The Duck" (Tufa Labs) = ajan REPL'de Python yazıyor
  (yerel Qwen). Frontier şu an LLM-in-the-loop; ama çekirdek fikir program yazmak.

---

## 2. Neden ağırlık DEĞİL, neden kör BFS DEĞİL

- **Ağırlık (YOLO gibi ağ):** veriden istatistik ezberler. Test oyunu yeni → ezberlenecek
  şey yok. Ağırlık = geçmişi hatırlamak; ARC = ilk kez görüleni çözmek. Çekirdek olamaz.
- **Saf BFS (aksiyon dizisi arama):** kural kurmaz, kör sayar. Kombinatorik patlar; ön koşul
  kavramı yok → "aa" anı yok. Zeka değil, enumerator.
- **Doğru şey = program sentezi:** oyunu açıklayan en kısa kuralı bir DSL içinde ara.
  Modelin "mantığı" = kendi yazdığı o kural.

---

## 3. Mimari (yazacağımız şey)

İki AYRI döngü — karıştırma:

```
İÇ DÖNGÜ  (ANLAMA)  → oyunun KURALINI ara       ← ZEKA BURADA (program sentezi)
DIŞ DÖNGÜ (OYNAMA)  → kuralı bilince HAMLEYİ ara ← BFS/A* burada, zararsız & ucuz
```

| Katman | Ne yapar | Araç | Ağırlık? |
|---|---|---|---|
| **Perception** | grid → nesneler + ilişkiler | bağlı bileşen (connected components) | ❌ yok |
| **DSL** | olası mantıkların dili (ilkel işlemler) | elle atom set + öğrenilen ilkeller | ❌ yok |
| **Sentez** | gözleme uyan EN KISA kuralı bul | program araması + Occam/MDL | ❌ yok — ZEKA BU |
| **Planner** | kuralı kullanıp hedefe git | BFS/A*/MCTS (öğrenilen model üstünde) | ❌ yok |
| **Rehber (ops.)** | "hangi hipotezi önce dene" | sezgi/heuristik VEYA LLM | ⚠️ sadece burada |

- Perception çıktısı = **tipli nesne modeli**: her nesne `{renk, hücreler, şekil imzası,
  konum, rol}` + ilişkiler (`aynı_mı, komşu_mu, içinde_mi, ...`).
- Sentez, gözlem havuzuna `(state, aksiyon → sonraki state)` uyan en yalın kural setini bulur.
- Planner, gerçek oyunda değil **öğrenilen kural üstünde** arar → hızlı ve anlamlı.
- Ağırlık/LLM ASLA çekirdek değil; sadece sentez aramasını yönlendiren pusula.

---

## 4. Şekiller / soyutlama ilkesi (kritik karar)

- **İsimli şekil sözlüğü (L, kare, yuvarlak) gömme → YANLIŞ.** Test şekilleri keyfi; ezber tuzağı.
- **Doğru:** şekli tam deseniyle (normalize bitmap) sakla; **isim değil, İLİŞKİ** ile kıyasla:
  `aynı_şekil, ayna_mı, dönmüş_mü, ölçekli_mi, aynı_renk`.
- Şekil hafızası **oyuna özel ve dinamik**: oyun başında boş, oynarken dolar, yeni oyunda sıfırlanır.
- Notlarda insan istediği kelimeyi kullanır (ayna/yuvarlak/zincir = geometrik → sorun değil;
  sadece "Nike'a benziyor" tarzı ezber-ikondan kaçın). Koda dökerken kelime → geometrik teste çevrilir.

---

## 5. "Aa" anlarının mekanizması (BFS/ağırlık üretemez)

Her "aa" 4 somut olaydan biri:

1. **Zıtlık-güdümlü kural daraltma (variable isolation):** tek değişkenin farklı olduğu iki
   gözlem, kuralın neye bağlı olduğunu açığa çıkarır.
   Örn lf52: sağdakine tıkla→sol'da oluşur / soldakine tıkla→sağ'da oluşur ⇒ "sonuç tıklananın zıddı".
   Zıt örnek ŞART.
2. **Occam / MDL sıkıştırma:** yeni kural birçok geçmiş gözlemi tek satıra indirir → "her şey
   yerine oturdu" hissi = daha kısa program tüm veriye uydu.
3. **Hedef regresyonu / araç-amaç analizi (means-ends, backward chaining):** istenen işlemin
   ön koşulu sağlanmıyorsa, onu sağlamayı yeni alt-hedef yap.
   Örn: "iki yeşil bir arada olmalı → üsttekini aşağı getirmeliyim."
4. **Analoji / soyutlama:** iki durum bir eşleme altında "aynı" → tek kural ikisini kapsar.

Zorluk: mekanizma net; asıl frontier = bu aramayı **insan kadar örnek-verimli** yapmak
(iyi DSL, iyi öncelik, ucuz zıtlık). Burada insan izleri + opsiyonel LLM-rehber yardım eder.

---

## 6. DSL ve KENDİ İLKELLERİNİ üretme (kuzey yıldızı)

- **Başlangıç DSL'i (elle):** atom işlemler —
  `bul, say, seç, aynı_mı, komşu_mu, içinde_mi, taşı(nesne,yön), renklendir, kopyala, sil,
  birleştir(a,b), yol_takip_et(nesne,renk), eğer <ilişki> ise`.
- **Kütüphane öğrenme (bootstrapped abstraction / DreamCoder mantığı):**
  1. Mevcut ilkellerle oyunları çöz.
  2. Çözümlerde **sık tekrar eden parçaları** bul.
  3. O parçayı **yeni bir ilkel** olarak kütüphaneye ekle (kristalize et).
  4. Tekrarla → sistem "merge", "ray-takip", "taşıyıcı" gibi kavramları KENDİ icat eder,
     hatta insanın adlandırmadıklarını.
- **Dürüst not:** hafif sürümü (tekrar eden aksiyon→etki kalıplarını makroya terfi) ulaşılabilir
  ve gerçekten bize vermediğimiz ilkeller bulur. Tam otonom "tüm insan bilgisini aşan" sürüm
  aspirasyonel — bu hafif sürümden ölçeklenir.
- **DSL'in ilkelleri nereden geliyor?** İnsan oyun notlarından. Birkaç farklı oyunda tekrar eden
  işlemler = DSL spec'i. (Birkaç oyunu önce oynamamızın gerçek sebebi bu.)

### 6.1. "Hiç atom vermesek, sıfırdan kurar mı?" — teorik taban

- **Literal "hiç" olmaz:** her zaman bir substrat (hesap dili) gerekir. Ama bu dil oyun-bilgisi
  İÇERMEYEBİLİR. İki tür taban:
  - Oyuna-özel atom: `birleştir, taşı, ray-takip` → **bunları VERME.**
  - Oyun-nötr evrensel taban: `hücre oku/yaz, karşılaştır, koşul, döngü, aritmetik` → **bu = anlamlı "sıfırdan".**
- **Turing-tam taban → teoride HER kuralı icat eder** (insanın görmediği kavramlar dahil).
  Bunun adı: **Solomonoff tümevarımı / AIXI** = var olan en genel öğrenici ("veriyi açıklayan
  en kısa programı bul"). Ama **hesaplanamaz** (intractable).
- **Bedel yasası:** ne kadar AZ verirsen o kadar ÇOK ararsın. Saf sıfırdan = pratikte patlar
  (muazzam rehber olmadan). Bedava öğle yemeği yok.
- **Pratik çözüm = DreamCoder / kütüphane öğrenme:** oyun-nötr minimal tabandan başla, tekrar eden
  çözüm parçalarını YENİ ilkel olarak kristalize et → sistem `birleştir/taşı/ray`i KENDİ kurar
  (bize sormadan). Gerçekten vermediğimiz kavramları üretir.
- **Bizim seçim:** en dibe (S-K combinator/lambda) inme — yarışma için hesaplanamaz. Oyun-nötr
  minimal taban ver:
  - VER (nötr): grid oku/yaz, nesne=bağlı bileşen (evrensel algı), koordinat aritmetiği,
    karşılaştır, koşul, nesneler üstünde döngü.
  - VERME (oyuna özel): birleştir, taşı(yön), ray-takip, seç → bunları kütüphane öğrenme bulsun.
  - İlke: **aranabilir kalan en dip tabanı seç.** Ne kadar dip → o kadar güçlü rehber (MDL + ops. LLM).

### 6.2. Atom döngüsü ve HIZ kısıtı (yeni atom kurmak asla uzun sürmemeli)

Döngü (lf52 örneği):
```
1. ÇÖZ (sentez):  L1'i ham atomlarla çöz → uzun program
                  seç(A); seç(B); [bitişikse] sil(A); sil(B); yaz(yeşil, zıt_taraf)
2. TEKRARI YAKALA: aynı blok L2, L3'te de çıktı (≥K kez)
3. KRİSTALİZE ET: bloğu tek yeni atoma paketle → 'birleştir(A,B)' (isim = numara, kendi icat etti)
4. DEVAM:         L4'te 'birleştir' tek adım → program kısa → arama sığ → hızlı çöz
                  sonra 'birleştir+taşı' tekrarı → 'taşıyıcıya_yükle' atomu → ...
```

**İki işi AYIR (hız için kritik):**

| İş | Maliyet | Ne zaman |
|---|---|---|
| Çözmek (sentez araması) | pahalı, üstel | oyun oynarken, 9sa bütçesinde |
| **Yeni atom kurmak (sıkıştırma)** | **ucuz, tek geçiş O(n)** | çözümler bulununca, arada |

- Yeni atom kurmak = **arama DEĞİL**; zaten bulunmuş çözümlerdeki tekrarı paketlemek
  (frekans sayımı + kalıp çıkarma / anti-unification). Program boyutuyla orantılı → asla uzun sürmez.
- Yeni atom = **geleceği hızlandıran yatırım:** büyük atom → kısa program → sığ arama → hızlı çözüm.
  Kütüphane öğrenme, sentezi hızlı tutan mekanizmanın ta kendisi.

**Tuzak — çok atom da yavaşlatır** (daha geniş dallanma). O yüzden:
- Sadece **sık kullanılan** (değerini ödeyen) parçayı atom yap.
- **MDL kapısı:** yalnızca toplam açıklamayı gerçekten kısaltıyorsa terfi et.
- **Kullanılmayan atomu buda** (kütüphane yalın kalsın).
- **Memoize/hash:** aynı şeyi iki kez türetme.
- Yani "asla uzun sürmesin" iki yönlü: atom kurma ucuz olsun HEM DE kütüphane şişmesin.

---

## 7. İnsan-izi metodolojisi

- İnsan (kullanıcı) oyunu **kör** oynar (ipucu yok), anladıklarını + aksiyonlarını txt'ye yazar.
- **Kaç oyun?** 25 değil. **Her tipten 1** yeterli (çeşitlilik lazım, sayı değil):
  1 click + 1 keyboard + 1 keyboard_click + 1 none = **4 oyun**, 1-2 seviye.
- Aksiyonlar makine-okur token: `[A0] [A1]..[A5] [A7]` ve `[A6@x,y]`. Regex: `\[A\d[^\]]*\]`.
- İki kullanım: (a) DSL ilkellerini keşfet, (b) ajan "insan gibi mi oynuyor" kıyası
  (insan izi ⟷ ajan izi).
- Sonra: kalan gizli oyunlarda ajanı dene = gerçek test (yarışmayı taklit eder).

**Oyun tipleri (referans):**
- click (7): lf52, lp85, r11l, s5i5, su15, tn36, vc33
- keyboard (4): g50t, ls20, tr87, wa30
- keyboard_click (13): ar25, bp35, cd82, cn04, dc22, ka59, m0r0, re86, sb26, sc25, sk48, sp80, tu93
- none (1): ft09

**Şu an seçili 4 oyun (dropdown, karışık sıra, tip gizli):** g50t, lf52, ft09, m0r0.

---

## 8. Player + Not aracı (KURULU)

- Dosya: `/home/adem/Desktop/AGI/player/server.py` (stdlib http.server, arc_agi venv).
- Çalıştır: `cd /home/adem/Desktop/AGI/ARC-AGI-3-Agents && uv run python ../player/server.py`
  → http://localhost:8000  (port: `PLAYER_PORT=9000`).
- Solda oyun (butonlar `0 1 2 3 4 5 7` + grid'e tık=ACTION6, ipucu YOK), sağda not defteri
  (`notes/<oyun>.txt`, otomatik kayıt).
- Her hücrenin üstünde **değeri (0-15)** kontrast renkle yazılı (renk adı yerine sayı kullan).
- **F3** = NOT ✍ ↔ OYUN 🎮 modu (odak için boşuna tıklama olmasın).
- Aksiyon → nota otomatik token, her aksiyon YENİ numaralı satıra.
- Seviye atlayınca 4 satır boşluk + `===== SEVIYE N =====` başlığı; numara her seviyede 1'den.
- **Seviye-devam:** oyunu tekrar açınca txt'deki en yüksek `SEVIYE N`'den başlar
  (set_level + `_action_count=1` ile level_reset hilesi; RESET full_reset yapmasın diye).

---

## 9. Yol haritası (kod adımları)

1. **perception.py** — grid → bağlı bileşen nesneleri + şekil imzası + ilişki fonksiyonları
   (`aynı_şekil, ayna_mı, dönmüş_mü, komşu_mu, içinde_mi`). Gerçek lf52 grid'inde doğrula
   (insan izi ⟷ ajan nesneleri yan yana).
2. **transition.py** — frame diff: aksiyon öncesi/sonrası nesne değişimi (taşındı/oluştu/
   kayboldu/renk değişti). Aksiyon anlamını denemeyle öğren.
3. **synthesize.py** — gözlem havuzundan DSL kuralı çıkar (zıtlık daraltma + Occam). İlk hedef:
   lf52'de `action4 → taşı(araç, sağ) EĞER sağında renk5 varsa` kuralını otomatik sentezle.
4. **goal.py** — `levels_completed` neyi artırıyor → hedef koşulu çıkar.
5. **planner.py** — öğrenilen kural + hedef → arama (rayda BFS/A*). Deneme-yanılma direksiyon YOK.
6. **library.py** — kütüphane öğrenme: sık çözüm parçalarını yeni ilkel olarak terfi et.
7. **agent.py** — hepsini bağla: keşif → sentez → plan → uygula → seviye transferi.
8. **Kaggle paketleme** — offline wheel, ≤9sa, gateway'e bağlan, submission üret.

---

## 10. Dizin haritası

```
/home/adem/Desktop/AGI/
├── plan.md                     ← bu dosya
├── environment_files/          25 oyun (<oyun>/<hash>/<oyun>.py + metadata.json)
├── arc_agi_3_wheels/           offline wheel'ler
├── ARC-AGI-3-Agents/           ajan çerçevesi (main.py, agents/, .venv = arc_agi)
└── player/
    ├── server.py               player + not aracı (KURULU)
    ├── work.txt                çalıştırma + kullanım notları
    └── notes/<oyun>.txt        insan oyun notları (izler)
```

---

## 11. Açık sorular / riskler

- **DSL tasarımı:** çok küçük → bazı oyunu ifade edemez; çok büyük → sentez patlar. İlkel
  vokabülerini doğru seçmek asıl zanaat (insan izleri buna spec).
- **Arama verimi:** sentez örnek-verimli olmalı; gerekirse LLM-rehber (takılıp çıkarılabilir).
- **LLM duruşu:** "asla LLM" DEME; "mecbur değilim ama kapıyı açık tutarım." Çekirdek sembolik,
  LLM sadece pusula. Frontier hibrit; tek elini bağlama.
- **Ölçek drift / kısmi gözlem:** bazı oyunlarda gizli durum olabilir; diff her şeyi vermez.

---

## 12. İnsan oyun keşfi (2026-07-19) — DSL için spec

- Player + not aracı kurulu ve çalışıyor; 4 oyun seçili (tip gizli).
- **lf52** insan tarafından çözüldü: Seviye 1-2-3 (WIN). Çıkarılan mekanik:
  seç → aynı yeşilleri birleştir → turuncu-12 taşıyıcıya yükle → siyah-5 ray'de sür → teslim.
  ACTION5 = tuzak (başa sarar). Yön: 1=yukarı 2=aşağı 3=sol 4=sağ (yalnız yol varsa).
  Öğrenme eğrisi görünür: L1=85, L2=56, L3=56 aksiyon (kafa karışıklığı → uygulamaya döndü).
- Bu insan izi, DSL ilkellerinin ("birleştir", "taşı", "ray-takip") **spec'i** — hangi
  mekaniklerin oyunlar arası tekrar ettiğini gösterir.

---

## 13. TOKENIZER MIMARISI (2026-07-19 — KALICI, silinmez)

Kullanicinin cekirdek vizyonu: her sey SAYI (token). Uzay-tokenizer / BPE mantigi.
Katmanlar sirayla kuruluyor: **sekil → olay → rol → iliski → dinamik → BIRLESIK token → plan**.

### 13.1. SEKIL tokenizer  ✅ BITTI  (agent/transition.py: ShapeVocab)
- IKI KATMANLI:
  - **ORNEK-TOKEN:** her (norm_mask, renk, MERKEZ-piksel/centroid) kendi tokeni.
    Birebir aynisi (ayni sekil+renk+merkez) tekrar -> ayni token. Konum(merkez) farkli -> YENI token.
  - **KUME:** olcek-bagimsiz oznitelik vektoru (P.features_shape, 9-boyut: aspect, fill,
    symh, symv, symd, rows_used, cols_used, |top-0.5|, |left-0.5|) + benzerlik esigi
    (threshold=0.22). Ayni sekil farkli RENK -> ayni kume. Farkli OLCEK -> ayni kume.
    AYNA -> ayni kume (oznitelik ayna-bagimsiz: merkeze uzaklik).
- Sekil x,y = piksellerin MERKEZI (centroid, round).
- KATMAN-2 BILESIK sekiller (P.find_compounds, gap=3): yakin+ayni temel sekiller
  birlesir -> bilesik nesne (BPE'nin 2B hali). Orn lf52: 28 gri kare -> tek 40x40 tahta.
  Hedef: piksel→sekil→bilesik→...→64x64'e kadar, durma noktasi SIKLIK.
- Denetci arayuz: agent/shape_inspector.py -> http://localhost:8002 (6 oyun, esik URL'den).
- SOZLUK OYUNA OZEL: her oyunda sifirdan (Mind her oyun yeni). Seviye degisince
  degisen sekillere gore buyur.
- Test dogrulandi: L / L-ayna / L-konum-farkli -> hepsi ayni kume; kare/cizgi ayri.
  6 oyun: 154 nesne -> 15 kume (katman1), 17 bilesik -> 9 kume (katman2).

### 13.2. OLAY tokenizer  ✅ var  (agent/transition.py: EventVocab, diff, Mind.observe)
- Diff: iki grid, nesneleri HUCRE-ORTUSMESIYLE esler. Degisim kayitlari (dict):
  effect, color, dir, before(obj), after(obj).
- Etki kodlari (sayisal): 0 NOCHANGE,1 MOVE,2 SHRINK,3 GROW,4 APPEAR,5 VANISH,
  6 MERGE,7 RECOLOR,8 WIN(seviye/oyun bitti),9 BACK(basa dondu=geri).
- OLAY = SAYISAL KUME-gecisi (insan etiketi YOK): sig=(action, effect, kume_once,
  kume_sonra, dir). Gosterim: "A6: K0 ▶ K1", "A4: K3 ⇒SAG", "⊕ ▶ K5", "★ BITTI".
- TEK-SEFERDE ogrenir (ilk goruste token), ASLA unutmaz, tekrarda sayac artar.
- BIRLESME tespiti: ayni renk >=2 kaybol + >=1 olus -> tek E_MERGE.

### 13.3. ROL tokenizer  ✅ YENI  (agent/transition.py: RoleModel)
- Rol = olayin USTUNDE 2. derece "anlama": nesne NE-yapiyor -> nesne NE-dir.
- Her KUME icin davranis profili biriktirir; 10-boyut DAVRANIS vektoru:
  [dur(agan), yon-hareketi, tik-degisimi, birlesme, sayac, dog/kaybol,
   goreli-boyut, (uzerinde-hareket=henuz0), seviye-tetikler, (engeller=henuz0)]
- Rol atama (esik-kural, sonra kumeleme de eklenebilir):
  arka plan(boyut>0.25 & dur>0.7) / hedef(lvl>0) / sayac(sayac>0.25) /
  kargo(birles>0.05) / hareketli(yon>0.15) / secilebilir(tik>0.2) /
  statik-yol-duvar(dur>0.8) / belirsiz.
- Test (180 adim kesif): m0r0 -> K0 ARKA PLAN(dur1.0,boy0.63), K3 SAYAC(0.84).
  lf52 -> K0 SAYAC, K1/K2 STATIK, K3/K4 SECILEBILIR. g50t -> K6 SAYAC.
  ARKA PLAN + SAYAC 3 oyunda da davranistan bulundu (biz etiketlemeden).
- Test araci: agent/role_test.py  (uv run python ../agent/role_test.py <oyun> <adim>)
- ACIK: "hareketli"/"kargo" kesifte tetiklenmedigi icin cikmadi; boyut 8(uzerinde-hareket)
  ve 10(engeller) uzamsal analiz gerektiriyor, sonra eklenecek.

### 13.4. SIRADAKI katmanlar (henuz YOK)
- **ILISKI tokenizer:** iki nesne arasi (A, B UZERINDE hareket eder = yol iliskisi;
  A engeller B; A icinde B). Uzamsal+zamansal birliktelikten.
- **DINAMIK model:** tek nesnenin durum-DIZISINE oruntu (sayac turu: iki-katli /
  hileli tek-katli / 5'li). Rol "sayac" der, dinamik "hangi tur sayac" der.
- **BIRLESIK TOKEN (EN SON):** her nesne icin sekil+olay+rol+iliski+dinamik'i
  ICINE ALAN tek token; her nesne icin FARKLI. Sadece sekil degil, hepsini kapsar.
- **PLAN beyni (EN SON):** birlesik tokenlar + hedef -> arama/plan -> oyunu bitir.

### 13.5. Gozlem arayuzu  (agent/brain_ui.py -> http://localhost:8001)
- 3 panel: sol GOZ(kume+gorsel), orta OYUN(64x64+sayilar), sag BEYIN(olay-token), alt EL.
- SPACE = ajan bir kesif adimi. Grid'e tik / rakam = kullanici surer.
- MERAK: yeni olay uretmeyen yeri tekrarlamaz. A0=geri ogrenir, spam etmez.
- 500-adim testi: ~6sn (84 adim/sn). NOT: planlayici henuz seviye 1'i GECEMIYOR
  (seyrek odul + karar katmani eksik). Temsil katmani saglam; plan katmani en sona kaldi.

### 13.6. GitHub (gunluk commit)
- Repo: /home/adem/Desktop/AGI  (git init). .gitignore ile BUYUKLER haric:
  ARC-AGI-3-Agents/, arc_agi_3_wheels/, environment_files/  (GitHub'a GITMESIN).
- GIDEN: agent/, player/, plan.md + gelecek klasorler.
- Her gun sonu commit. (Kurulum surerken classifier kesildi; tamamlanacak.)

---

## 14. denme/ — Karar/keşif yöntemi yarışması (2026-07-19/20)

> Temsil katmanı (§13) sağlamdı ama **hiçbir plan katmanı seviye geçemiyordu.** Bu yüzden
> orijinal `agent/`'a DOKUNMADAN, `denme/` altında kopya altyapıyla **20+ karar yöntemi**
> yarıştırıldı. Amaç: saf matematik/olasılık (LLM YOK, ezber YOK) ile ilk seviyeyi geçmek.

### 14.1. Altyapı
- `denme/infra/` = perception.py, action.py, transition.py kopyaları (orijinal bozulmasın).
- `env.py`: hızlı headless ortam (HTTP/UI yok, ~150–220 adım/sn). `candidates()` tüm
  tuşları + nesne-başı tık (size≤200) sunar.
- `bench.py`: metrikler {max_level, coverage, events, merges, min_obj, goal_drop}.
- `strategies.py`: 13 klasik yöntem. `strategies2.py`: makro/eleme yöntemleri.

### 14.2. Round 1 — 13 klasik yöntem (1500 adım × 2 tohum × 3 oyun)

| # | Yöntem | Skor | Kapsam | Olay | Seviye |
|---|--------|------|--------|------|--------|
| 1 | **Go-Explore** | 42.9 | 304 | 78 | 0 |
| 2 | Novelty-Search | 40.3 | 183 | 72 | 0 |
| 3 | Thompson | 39.6 | 187 | 70 | 0 |
| 4 | Belief-InfoGain | 39.2 | 192 | 68 | 0 |
| 5 | Random | 37.9 | 182 | 66 | 0 |
| … | (efe/curiosity/empowerment/model_plan) | 13.7 | 130 | 18 | 0 |

**Go-Explore keşifte açık ara galip** (m0r0'da 477 vs ~100 = 4.5 kat). Reset-only
ortamımıza doğal uyum (arşivle + umut veren duruma dön + oradan keşfet).

### 14.3. KRİTİK BULGU — darboğaz keşif değil, MAKRO
- **13 yöntemin HİÇBİRİ hiçbir oyunda seviye geçemedi**, hiç birleşme üretemedi (5000 adımda bile).
- **TÜM yöntemler m0r0'da min_obj=2'ye iniyor** — yani "2 nesne kaldı" eşiğine herkes
  ulaşıyor ama **son koordineli birleştirmeyi** yapamıyor.
- Açgözlü sömürü yöntemleri (efe/curiosity) EN KÖTÜ (kapsam 130) — ödül yokken çöküp tekrara giriyor.
- **Ders:** Sorun "hangi keşif bonusu" değil. Eksik olan **tek-aksiyon değil aksiyon-DİZİSİ
  (makro)** keşfi. Tek-adım keşif "seç→hedef→uygula" çiftini zincirleyemiyor.

---

## 15. KIRILMA — Yanlış-Eleme + Ödül (kullanıcının fikri) ✅ İLK SEVİYE GEÇEN

### 15.1. Fikir (kullanıcının)
> Doğru cevap TEK ve gizli → bulmak zor. Ama YANLIŞ bol ve hedefi bilmeden görülür
> (etki-yok / geri-dönüş / game-over). **"Tüm yanlışları ele, geriye doğru kalır."**

### 15.2. Mekanizma (`strategies2.py`: `I_wrong_elim_reward`)
- **W[bağlam-token, aksiyon]** = 1.0'dan başlar, SADECE yanlışta düşer (×0.15 = BETA). Bayes eleme.
- Bağlam ZENGİN: `(6, şekil-token)` = tık ayrı, `(n, -1)` = tuş ayrı → tık/tuş ayrı elenir.
- **YANLIŞ (ele):** etki-yok / görülen duruma geri-dönüş / game-over.
  **YANLIŞ DEĞİL:** herhangi yapısal değişim → çok-adımlı doğru hamleyi KORUR (elemez).
- Yeni şekil → yeni token → W=1 (TAZE, elenmez). Seviye atlayınca eski elemelere 2. şans (×4 revive).
- Ödül: yeni durum (+0.3), seviye-atlama (+10, kredi ataması geriye). Go-Explore omurga.
- Bağlam TOKEN → genelleşir. Her oyunda sıfırdan. **EZBER YOK, önceden-eğitim YOK.**

### 15.3. SONUÇ — 25 oyun taraması (1800–3000 adım, 2 tohum)

**SEVİYE GEÇEN (4/25):**

| Oyun | Tip | Ulaşılan seviye | Güven |
|------|-----|-----------------|-------|
| **vc33** | click | **seviye 2** | 5/5 tohum güvenilir |
| **cd82** | kb-click | seviye 1 | geçti |
| **tn36** | click | seviye 1 | geçti (kapsam 1498) |
| **r11l** | click | seviye 1 | geçti (kapsam 1311) |

**Geçemeyen (21/25):** lf52, m0r0, g50t, ft09, lp85, s5i5, su15, ar25, bp35, cn04,
dc22, ka59, sc25, sk48, sp80, tu93, sb26, re86, tr87, ls20, wa30.

### 15.4. Analiz
- **Geçen 4:** kısa tık-dizisiyle ilerleyen tipler (tıkla→desen eşle / renk değiştir).
  Yanlış-eleme doğru tıklamayı hızla buluyor.
- **Geçemeyen 21:** uzun koordineli dizi gerektiren tipler (kargoyu ray'de sür, çok-adımlı
  taşıma). Makro/dizi problemi burada da duruyor (§14.3 ile aynı duvar).
- **Değerlendirme:** Bu, tüm oturumun **ilk seviye-geçen** yöntemi. 4/25 = %16 (biri sv2),
  saf sıfırdan-sembolik, ezbersiz. Kullanıcının "yanlıştan öğren" sezgisi çalıştı.
- Canlı izleme: `live.py` → http://localhost:8005 (SPACE adım; W ağırlıkları, elenen
  aksiyonlar, ödül kredisi canlı).

---

## 16. VSA / TPR beyni — "her şey vektör" (kullanıcının son vizyonu)

> Kullanıcı: *"Gerçek hayattan bilgi verme, kod otomatize etme (aşağı-hareket gibi) YOK;
> her şeyi vektörlerle yap, en son bir vektöre sok, çıkış 1–7 aksiyon, döngüye gir,
> AMA aşırı hızlı öğrensin."* → **Vektör Sembolik Mimari (hiperboyutlu hesaplama).**

### 16.1. Çekirdek (`denme/vsa.py`) — DOĞRULANDI
- MAP modeli, bipolar {−1,+1}, **D=10000**. Metin/gradyan/LLM YOK.
  - `bind(a,b)=a*b` (rol↔değer eşle, kendi-tersi) · `bundle=sign(Σ)` (küme/yapı)
  - `unbind=a*r` (bind kendi-tersi) · `permute=roll` (sıra) · `sim=<a,b>/D`
  - `ItemMemory`: isimli atom + `cleanup` (gürültülü vektörü en yakın atoma çevir).
- Doğrulama: atomlar ~dik (0.004), bind→unbind geri getirir (1.0), bundle üyeliği çalışır.

### 16.2. Hiyerarşik bilgi (`denme/knowledge.py`) — kullanıcının vizyonu
`piksel → ŞEKİL → NESNE → SAHNE → KURAL → en büyük bilgi`. Her seviye alt seviyelerin bind+bundle'ı:
- **NESNE** = bind(şekil)+bind(renk)+bind(konum) → tek vektör (model "yeşil" bilmez;
  "bu rolde bu şekil" bilir).
- **SAHNE** = tüm nesnelerin permute'lu bundle'ı → tek vektör.
- **KURAL** = `(aksiyon, ÖNCE) → SONRA` bind. **TEK-ATIŞTA** öğrenilir, cebirle KULLANILIR:
  `predict_after(a, önce) = unbind(kural, (aksiyon,önce)) ≈ SONRA`.
- Doğrulama: tek-atış kural sim=1.0; **renk-bağımsız yapısal genelleme** çalıştı
  (iki-yeşil kuralı → iki-mavi'ye ~0.49 transfer).

### 16.3. VSA ajanı (`denme/vsa_agent.py`)
- Her adım: grid→sahne vektörü; aksiyon→yeni sahne; kural tek-atışta öğren; karar:
  `w × (novelty + 0.3×plan_val)` (plan_val = tahmini sonra ne kadar değişecek). Yanlış-eleme W korunur.
- **Sonuç:** tn36 + r11l geçti (2/4 kıyas). vc33/cd82 **eleme dengesi bozununca düştü** → AYAR GEREK.
- Geniş tarama (12 oyun, 2 tohum): **2/12** seviye geçti (tn36, r11l).

### 16.4. Son kıyas (4 oyun, 1200 adım, tek tohum)
| Oyun | Yanlış-eleme (I) | VSA-beyin |
|------|:---:|:---:|
| vc33 | ✅ sv1 | — |
| cd82 | — | — |
| tn36 | ✅ sv1 | ✅ sv1 |
| r11l | ✅ sv1 | ✅ sv1 |
| **GEÇEN** | **3/4** | **2/4** |

> Not: kısa/tek-tohum koşu; uzun bütçe + çok tohumla yanlış-eleme vc33 sv2 + cd82'yi de geçiyordu.
> Bu tablo "hızlı" hali. Yanlış-eleme şu an önde; VSA'nın eleme dengesi ayarlanınca eşitlenmeli.

---

## 17. YARIN / SIRADAKI (öncelik sırasıyla)

1. **VSA eleme dengesi:** vc33 + cd82'yi geri kazan (I_wrong_elim seviyesine getir) +
   VSA tahminini (`predict_after`) karara DAHA güçlü kat (0.3 → dinamik). Şu an tahmin
   sadece zayıf rehber; model-tabanlı planı öne çıkar.
2. **MAKRO / besteleme (asıl duvar):** geçemeyen 21 oyunun ortak sorunu uzun koordineli dizi.
   - Go-Explore + **2–3 aksiyonluk dizi** dene (tek aksiyon değil) → "seç→hedef" çifti.
   - VSA'da **kuralı zincirle:** `predict_after`'ı ardışık uygulayıp çok-adımlı sonucu öngör.
   - Yanlış-elemeyi **DİZİ üzerinde** yap (tek aksiyon değil, makro ele/canlı tut).
3. **Büyük doğrulama testi:** 25 oyun × çok tohum × uzun bütçe. `nohup` erken kesiliyor →
   **senkron küçük gruplar** halinde koştur (kanıtlanmış çözüm).
4. **Go-Explore hücre tanımını kabalaştır:** tam grid-fp yerine (nesne-sayısı + kümeler) →
   anlamlı durumlar arşivlensin, gürültü değil.
5. **ft09 (desen-eşleştirme) özel:** yön yok, sadece tık; hedef "şablon eşle" → goal-hipotez
   diline **şablon-eşleştirme** eklenmeli (min_count/min_obj yetmiyor).
6. **Derin açık soru:** "hangi değişmezlik tanımlayıcı, hangisi tesadüfi" — kavram-başına
   ÖĞRENME (Tog örneği). Şu an değişmezlikler sabit kodlu; ideal: oyundan öğrensin.

### Dosya haritası (denme/)
```
denme/
├── infra/               kopya perception/action/transition (orijinal bozulmasın)
├── env.py               hızlı headless ortam
├── bench.py             metrikler
├── strategies.py        13 klasik yöntem (Go-Explore galip)
├── strategies2.py       makro/eleme — I_wrong_elim_reward = KAZANAN
├── vsa.py               VSA çekirdek (D=10000, bind/bundle/unbind) — doğrulandı
├── knowledge.py         hiyerarşik bilgi (piksel→şekil→nesne→sahne→kural)
├── vsa_agent.py         VSA ajanı (tek-atış kural + tahmin + eleme)
├── live.py              canlı UI → localhost:8005
├── REPORT.md            tam rapor · SONUCLAR.json  tam metrikler
├── solver/              SMT/CEGIS görevi (§18) — predicates/learn/cegis/bisim
└── *.log                broadtest / vsa_broad koşu kayıtları
```

---

## 18. SMT + CEGIS + Bisimülasyon görevi (2026-07-25) — solver_gorev.md

> Tam ölçümler: `denme/solver/SONUC.md` · ayarlar: `denme/solver/AYAR.md`

- **FAZ 1 (MaxSAT kural öğrenme): ✅ KABUL GEÇTİ.** vc33'te 6/6 etki, doğruluk
  0.84–0.98, <0.2sn/kural. KRİTİK BULGU: tek VE-kuralı yetmez — mekanikler AYRIK
  ("s1 VEYA s2'ye tıkla") → kural LİSTESİ (ardışık kapsama) + polarite şart.
  `unseparable` sinyali iki ayrı teşhis verdi: form eksiği + gizli durum.
- **FAZ 2 (CEGIS deney seçimi): ❌ KABUL GEÇEMEDİ.** 0/4 oyunda kazanç, cd82'de
  seviye kaybı. Yapısal neden: ilk WIN'den önce sömürülecek kural yok; doğru
  tahmin ≠ daha iyi karar. Ablasyon dersi: sınırsız deney SEVİYE KAYBETTİRİR.
- **FAZ 3 (makro): şartname kapısı gereği İNŞA EDİLMEDİ** (plan.py = gerekçe).
- **BİSİMÜLASYON (ek): 0.22 eşiksiz davranışsal denklik — 2/4 oyunda EZDİ:**
  tn36 %63, r11l %83'e varan daha az aksiyon; ama vc33'te sv2'yi kaybetti
  (gizli-durumlu oyunda davranış imzası yanıltıcı). Tek kip evrensel değil →
  sıradaki iş: determinizme göre kip seçen UYARLANIR bisimülasyon.
- z3 offline wheel hazır (`solver_wheels/`), Kaggle bütçe/timeout korumaları çalışıyor.

---

## 19. Hedef hipotezi + meta + şema görevi (2026-07-25) — hedef_gorev.md

> Tam ölçümler: `denme/goal/SONUC2.md`. Motivasyon: FAZ 2 "seviye-1-öncesi
> sömürülecek şey yok" dedi — çünkü ajan hedefi ARAYARAK buluyordu. İnsan ise
> hedefi İLK KAREDE, aksiyonsuz, geometriyle kuruyor. Bu görev onu mekanikleştirdi.

- **Modül A (goals.py) — hedef hipotezi: ✅ 4/4 (aksiyonsuz).** 5 oyun-nötr geometrik
  şablon (UNIFY/FIT/OVERLAP/CONSISTENT/COLLECT). İlk karede insan hedefiyle eşleşen
  hipotez ilk 2 sırada: m0r0→UNIFY, g50t→FIT, ar25→OVERLAP, lf52→COLLECT.
  **Notun tezi kanıtlandı: dünya bilgisi olmadan saf sayıyla hedef kuruldu.**
- **Modül B (meta.py) — sayaç/tehlike/bağlaşık: ✅ 4/4.** ft09/m0r0 sayaç,
  g50t A5-tehlike, ar25 coupled. Hepsi sayım/geometri, oyun adı geçmiyor.
- **Modül C (schema.py) — şema/φ: çekirdek ✅, transfer ⚠️.** ft09'da CONSISTENT
  tespiti φ={0→8,2→9} çıkardı = insan eşlemesiyle BİREBİR (aksiyonsuz). Ama ft09
  sv1 geçilemediği için sv2-transfer ölçülemedi.
- **Entegrasyon (goal_agent.py): ❌ 0/5 yeni oyunda sv1.** Sert gerileme yok
  (tn36/r11l/cd82 sv1 korundu). **KESİN DERS: darboğaz artık "hedefi bilmemek"
  DEĞİL — saf PLANLAMA.** Model-free progress-tepe-tırmanışı makro duvarını kıramıyor
  (ar25: OVERLAP progress 0.10'da plato). Girdiler (kural FAZ 1 + hedef) hazır;
  eksik olan çok-adımlı arama (BFS/A*/SAT-plan).

### GENEL DURUM (iki görev sonrası)
Perception + şekil + olay + rol + **hedef** + **meta** + kural-öğrenme katmanları
ÇALIŞIYOR. Seviye geçen tek yöntem hâlâ **I_wrong_elim_reward** (4/25, yanlış-eleme).
Tüm gelişmiş katmanların tosladığı TEK duvar net: **planlayıcı** (öğrenilen kural +
hedef üstünde koordineli çok-adımlı arama). Sıradaki iş kesinlikle bu.
