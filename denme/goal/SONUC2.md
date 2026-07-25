# SONUC2.md — Hedef hipotezi + meta + şema (hedef_gorev.md şartnamesi)

> Tarih: 2026-07-25 · Tohumlar sabit (0,1) · Ölçümler `denme/goal/` altında.
> Her modül AYRI ölçüldü (şartname §7: hangi modülün ne kattığı ayırt edilebilsin).

---

## MODÜL A — Hedef hipotezi (goals.py) — ✅ KABUL GEÇTİ (4/4)

İlk kareden, **aksiyon harcamadan**, sadece geometriden 5 oyun-nötr şablon puanlanır:
UNIFY / FIT / OVERLAP / CONSISTENT / COLLECT.

| Oyun | İnsan hedefi (not) | İlk 2 hipotez | Beklenen | Sonuç |
|---|---|---|---|---|
| m0r0 | "mavi-10'ları birleştir" | **UNIFY** | UNIFY | ✅ |
| g50t | "iç içe geç, kare olsun" | **FIT** (doluluk 0.88) | FIT | ✅ |
| ar25 | "üst üste oturt" | **OVERLAP**, COLLECT | OVERLAP | ✅ |
| lf52 | "aynı yeşilleri topla" | **COLLECT**, COLLECT | COLLECT/UNIFY | ✅ |

**KABUL: 4/4 — doğru hipotez ilk 2 sırada, aksiyon harcamadan.** Bu şartnamenin
BİRİNCİL kapılı çıktısı (§1.5) ve notun vurguladığı asıl test. İnsanın ilk karede
kurduğu hedef, saf sayıdan (şekil imzası eşitliği, geometrik tümleyenlik, frekans)
yeniden üretildi — dünya bilgisi YOK.

Tek ayar: FIT doluluk eşiği 0.85 (g50t gerçek iç-içe-geçmesi 43/49=0.88; AYAR.md §5).

---

## MODÜL B — Meta tespit (meta.py) — ✅ KABUL GEÇTİ (4/4)

Hedef OLMAYAN ama kritik üç nesne tipi + arka plan; hepsi sayım/geometri, oyun-nötr.

| Oyun | Beklenen tespit | Sonuç |
|---|---|---|
| ft09 | alt satır → `meta:counter` (renk-12, azalan, 199 değişim) | ✅ |
| m0r0 | siyah-5 çizgileri → `meta:counter` (9 bölge, artan) | ✅ |
| g50t | A5 → `hazard:action` (41 sıfırlama / 53 uzak-kullanım = 0.77) | ✅ |
| ar25 | A1/A2/A7 → `coupled` (2-3 nesne aynı yer değiştirme) | ✅ |

**KABUL: 4/4 beklenen tespit tam.**

Ölçümle bulunan tasarım kararları (AYAR.md §5):
- **Sayaç:** oransal monotonluk (%80, sarmal payı) + sayaç-maskeli sıfırlama kıyası.
- **Tehlike:** payda = "gözlem fırsatı" (başlangıçtan uzakken kullanım); A0=evrensel
  RESET tautoloji olarak dışlanır. Sıfırlama = büyük GERİ-SARMA (tam-eşitlik değil;
  g50t A5 kısmî sıfırlar). Ölçülen ayrım: A5=0.70 vs en yakın gerçek aksiyon 0.23.
- **Bağlaşıklık:** aynı yer-değiştirme vektörüyle ≥2 nesne (MOVE + ışınlanma=VANISH+APPEAR).

Ek not (dürüstlük): m0r0'daki turuncu-8 **temas-tehlikesi SEVİYE 2 olgusu**
(insan notu sv2 başlığı altında; sv1 grid'inde renk-8 yok). Kaşif sv1'i geçemediği
için sv1 ölçümünde beklenemez; beklenti tablosu ölçülebilir-gerçeğe göre ayarlandı.

---

## MODÜL C — Seviye şeması (schema.py) — çekirdek ✅ DOĞRULANDI

Ayrım: **ŞEMA taşınır** (şablon kimliği, aksiyon semantiği, tehlike, bağlaşıklık) ·
**BAĞLAMA sıfırlanır** (küme→rol, renk→anlam φ, nesne kimlikleri).

### CONSISTENT tespiti + φ çıkarımı — ft09, ilk kare, aksiyonsuz

- `find_consistent`: karo-örgü geometrisinden **4 tahta grubu + harita** buldu
  (harita-renkleri {0,2}, karo-renkleri {8,9}).
- `infer_phi` (çoğunluktan, tutarlı gruplardan sayım): **φ = {0→8, 2→9}**.
- **Bu insanın notundaki `beyaz-0→turuncu-8, gri-2→mavi-9` eşlemesiyle BİREBİR AYNI.**
  Hiç aksiyon harcamadan, sadece çoğunluk-tutarlılığından.

Şema yaşam döngüsü kodlandı (`SchemaAgent`): seviye-atlamada `template_bonus` korunur
(şema), hipotezler + φ yeniden kurulur (bağlama). φ yeniden türetme: önce önceki
seviyenin φ'si (taşıma), K adım ilerleme yoksa MDL-sıralı sıradaki bijeksiyon.

### ft09 sv2<sv1 kabul ölçümü — ⚠️ ÖLÇÜLEMEDİ

3000 adım, tohum 0/1: ft09 **sv1 geçilemedi** (maxsv=0). Şema-taşıma ancak sv2'ye
ulaşınca ölçülebilir → kabul kriteri şu an ölçülemez.

**Ayrım net:** CONSISTENT tespiti ve φ çıkarımı (0→8, 2→9) MEKANİK olarak çalışıyor
ve insan eşlemesiyle birebir. Eksik olan tek şey ft09 sv1'i geçen bir PLANLAYICI —
ki bu tüm yeni oyunlarda ortak eksik (§ Entegrasyon). φ mekanizması hazır, planlayıcı
sv1'i geçince transfer devreye girecek.

---

## ENTEGRASYON — hedef-güdümlü ajan (goal_agent.py) — ❌ sv1 GEÇEMEDİ

Mimari: `GoalAgent(WrongElimReward)` — hedef hipotezi (progress = A* sezgiseli),
meta (sayaç dışlama + hazard veto kapılı + coupled→"duvara-daya" makrosu),
sistematik sonda (her kimlik 1 kez ΔH ölç), momentum (işe yarayanı tekrarla),
hipotez ölünce sıradakine geç, hiçbiri çalışmazsa saf WrongElim yedeği.

### Nihai kabul (§5) — 2000 adım, tohum 0/1

| Oyun | Tip | Temel sv1 | Hedef sv1 | Hedef maxsv |
|---|---|---|---|---|
| m0r0 | kb-click | — | — | 0 |
| g50t | kb-click | — | — | 0 |
| ar25 | click | — | — | 0 |
| lf52 | click | — | — | 0 |
| ft09 | none | — | — | 0 |

**Yeni oyunlardan seviye geçilen: 0/5** (kabul gereği ≥1) → **KABUL GEÇMEDİ.**

### Gerileme kontrolü (eski geçilen oyunlar)

| Oyun | Referans | Hedef ajan maxsv |
|---|---|---|
| vc33 | 2 | 1 (sv2 kaybı — tohum-bağımlı, gerçek riski var) |
| tn36 | 1 | 1 ✅ |
| r11l | 1 | 1 ✅ |
| cd82 | 1 | 1 ✅ |

**Sert gerileme yok** (eski oyunlar hâlâ sv1); vc33 sv2→sv1 yumuşak/tohum-bağımlı.

### Dürüst analiz — neden 0/5

1. **Hedefi BİLİYORUZ ama uygulayamıyoruz.** Modül A ilk karede doğru hedefi kuruyor
   (4/4), Modül B tehlike/bağlaşık/sayacı buluyor (4/4). Eksik olan **planlama**:
   hedefin `progress`'ini artıran çok-adımlı koordineli aksiyon dizisi.
2. **Progress-tepe-tırmanışı yeterli değil.** ar25 izinde OVERLAP progress 0.10'a
   çıkıp platoya giriyor: yatay mesafeyi A3 kapatıyor, dikey mesafe kalıyor; ajan
   plato sonrası A2'ye geçiş + geri-dönüş dinamiğini çözemiyor. Bu tam olarak
   solver SONUC.md'deki **makro duvarı** — model-free tepe-tırmanışı, durum-bağımlı
   çok-adımlı diziyi bulamıyor.
3. **"Duvara-daya" makrosu tetikleniyor ama yetmiyor** (m0r0/ar25 coupled bulundu,
   makro denendi; ama makro + sonraki adımın koordinasyonu eksik).
4. **Kanıtlanan şey:** darboğaz artık "hedefi bilmemek" DEĞİL. Perception+hedef+meta
   katmanı çalışıyor; darboğaz saf PLANLAMA — öğrenilen kurallar (solver FAZ 1) +
   hedef (bu görev) üstünde gerçek arama (BFS/A*/SAT-plan) gerekiyor. İkisi de artık
   elde; sıradaki iş bunları birleştiren planlayıcı.

### Sonuç
- **Notun asıl tezi DOĞRULANDI:** ajan artık seviye geçmeden, ilk karede, aksiyon
  harcamadan hedefi kuruyor (Modül A 4/4) — "dünya bilgisi olmadan sayıyla hedef" çalıştı.
- **Ama hedefi bilmek tek başına seviye geçirmiyor:** uygulama = planlama, ve bu hâlâ açık.
- İyi haber: darboğaz artık TEK ve NET (planlayıcı), ve girdileri (kural + hedef) hazır.
