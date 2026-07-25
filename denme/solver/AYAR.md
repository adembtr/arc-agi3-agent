# AYAR.md — public oyunlara bakılarak yapılan ayarlar (şartname §7 gereği)

> Her madde bir aşırı-uyum riski. Gizli oyunlarda geçerliliği sorgulanmalı.

## 1. Kural LİSTESİ (DNF, ardışık kapsama) — vc33 teşhisiyle eklendi
- Şartnamenin tek-VE-kuralı (2.4) vc33'te TÜM etkiler için `unseparable` çıktı.
- Teşhis: pozitifler birden çok odak-kümeye yayılıyor (AYRIK yapı — "s1'e TIKLA
  VEYA s2'ye TIKLA") → tek conjunction bunu ifade EDEMEZ. Havuz eksiği değil,
  form eksiği.
- Çözüm: `learn_ruleset` — kalan pozitiften tohum seç, tohumu tüm negatiflerden
  ayıran EN KISA kuralı Z3 ile çöz, kapsananları düş, tekrarla (≤6 terim).
  Her terim hâlâ MaxSAT-minimal; Occam korunuyor.
- Genellik değerlendirmesi: DNF öğrenme oyun-nötr bir form genişletmesi,
  vc33-özel bir sabit değil. Risk DÜŞÜK.

## 2. Polarite (çoğunluk-varsayılan) — vc33 teşhisiyle eklendi
- vc33'te azaldı/büyüdü etkileri neredeyse HER adımda oluyor (1144p/33n).
  "Ne zaman OLUR"u 6 terimle kapsamak imkânsız; doğru soru "ne zaman OLMAZ".
- Çözüm: pozitif > negatif ise sınıfları takas et, kuralı "E OLMAZ" için öğren,
  tahmini tersine çevir.
- Genellik: sınıf-dengesizliği standardı, oyun bilgisi içermiyor. Risk DÜŞÜK.

## 3. Yüklem havuzu genişletmesi — vc33'ün aynı-vektör çakışması sinyaliyle
- 160 satırda AYNI vektör hem pozitif hem negatifti (gizli durum sinyali).
- Eklenen yüklemler (hepsi oyun-nötr): `exists_color_v` (sahnede renk v var),
  `focus_color_count_gt1`, `focus_cluster_count_gt1`, `focus_color_eq_bg`,
  `focus_is_largest`, `focus_is_smallest`.
- Çakışma tamamen çözülmedi (E7'de hâlâ p100/n152 gürültü) → vc33'te gerçek
  gizli durum var (görünür karede olmayan bilgi). Kural listesi gürültüyü
  dışarıda tutup kalanını öğreniyor.
- Risk DÜŞÜK: "sahnede hangi renkler var" evrensel bir gözlem.

## 4. Sabitler
- `MAX_CLUSTER_SLOTS=32`, `SIZE_THRESHOLDS={4,16,64,256}`, `NOBJ_THRESHOLDS={2,4,8,16}`
  şartnameden. `SMALL=200` env.candidates ile tutarlılık için.
- `max_rules=6` (kural listesi üst sınırı): keyfî; büyütmek aşırı-uyum,
  küçültmek kapsam kaybı. vc33 dışında da bu değerle ölçülmeli.
