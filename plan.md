# ARC-AGI-3 — Proje Planı (mantık-tabanlı ajan)

> Amaç: Yarışmayı kazanmak. Yaklaşım: **kural + arama (program sentezi)**, ağırlık değil.
> Felsefe: Modelin "zekası" = veriden ezber (ağırlık) ya da kör hamle arama (BFS) DEĞİL;
> **oyunun mantığını kanıttan deşifre edip kurmak.** Bunu bir kere iyi kurarsak,
> hiç görülmemiş oyunları da çözer.

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

## 12. Şu anki durum (2026-07-19)

- Player + not aracı kurulu ve çalışıyor; 4 oyun seçili (tip gizli).
- **lf52** insan tarafından çözüldü: Seviye 1-2-3 (WIN). Çıkarılan mekanik:
  seç → aynı yeşilleri birleştir → turuncu-12 taşıyıcıya yükle → siyah-5 ray'de sür → teslim.
  ACTION5 = tuzak (başa sarar). Yön: 1=yukarı 2=aşağı 3=sol 4=sağ (yalnız yol varsa).
  Öğrenme eğrisi görünür: L1=85, L2=56, L3=56 aksiyon (kafa karışıklığı → uygulamaya döndü).
- Sıradaki: lf52'yi ~10. seviyeye taşı + farklı tipten oyunları oyna → sonra perception.py.

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
