# GÖREV: SMT tabanlı kural öğrenme + CEGIS deney seçimi (ARC-AGI-3)

> Bu dosya bir uygulama şartnamesidir. Kodu yazacak ajan için.
> Proje kökü: `/home/adem/Desktop/AGI/`
> Yeni kodlar: `denme/solver/` altına. **Mevcut hiçbir dosyayı bozma.**

---

## 0. BAĞLAM (önce oku)

Proje ARC-AGI-3 yarışması için sembolik bir ajan. Mevcut durum:

- `denme/infra/` — perception.py (grid → bağlı bileşen nesneleri), transition.py (frame diff → olay kodları), action.py
- `denme/env.py` — hızlı headless ortam, ~150-220 adım/sn, `candidates()` tüm aday aksiyonları verir
- `denme/strategies2.py` — `I_wrong_elim_reward`: şu anki en iyi yöntem, 4/25 oyunda seviye geçiyor
- `denme/vsa.py` — Vector Symbolic Architecture çekirdeği (D=10000, bind/bundle/unbind), doğrulanmış
- `denme/vsa_agent.py` — VSA ajanı, 2/12 oyunda seviye geçiyor

**Ölçülmüş darboğaz:** 20+ keşif yöntemi denendi, hiçbiri uzun koordineli aksiyon dizisi
(makro) gerektiren 21 oyunu geçemedi. Sorun keşif bonusu değil; sorun (a) geçiş kuralının
öğrenilememesi ve (b) hangi deneyin yapılacağına karar verilememesi.

**Bu görevin amacı:** kural öğrenmeyi elle yazılmış aramadan bir SMT çözücüye devretmek,
ve hangi aksiyonun harcanacağını CEGIS ile seçmek.

**Neden önemli:** yarışma skoru `min(insan_aksiyon/ajan_aksiyon, 1.0)²`. Boşa harcanan her
aksiyon karesel ceza. Aksiyon başına bilgi kazancını maksimize etmek doğrudan skordur.

---

## 1. ÖN KOŞULLAR

```bash
pip install z3-solver
```

Doğrula (bu çalışmalı):

```python
from z3 import Optimize, Bool, Not, Or, If, IntVal, sat
o = Optimize()
a, b = Bool('a'), Bool('b')
o.add(Or(a, b))
o.minimize(If(a, 1, 0) + If(b, 1, 0))
assert o.check() == sat
print(o.model())
```

**Kaggle notu:** internet kapalı. `z3-solver` wheel'ini şimdiden indirip
`arc_agi_3_wheels/` yanına koy, offline kurulumu test et. Bu adımı atlama.

---

## 2. FAZ 1 — MaxSAT ile kural öğrenme

### 2.1 Ne öğreniyoruz

Tek bir hedef etki `E` için (örn. `MOVE_RIGHT`, `MERGE`, `LEVEL_UP`) şu formda bir kural:

```
EĞER <koşul> İSE  E olur
```

`<koşul>` = **yüklemlerin (predicate) VE'lenmiş hali** (conjunction).
Amaç: tüm gözlemlerle tutarlı **EN KISA** koşulu bulmak.

### 2.2 Yüklem havuzu (`denme/solver/predicates.py`)

Her `(durum, aksiyon)` çifti için boolean bir öznitelik vektörü üret. Yüklemler
**oyun-nötr** olmalı — hiçbiri belirli bir oyuna özel bilgi içermemeli.

Üretilecek yüklemler:

**Aksiyon üzerine**
- `act_eq_k` — k ∈ 0..7

**Odak nesne üzerine** (aksiyon 6 ise tıklanan nesne; değilse her hareket adayı nesne)
- `cluster_eq_c` — c ∈ o ana kadar görülen küme id'leri
- `color_eq_v` — v ∈ 0..15
- `size_lt_T` — T ∈ {4, 16, 64, 256}
- `at_border_{left,right,top,bottom}`
- `neighbor_{up,down,left,right}_color_eq_v` — v ∈ 0..15   ← **kritik**, "yol varsa hareket eder" tipini yakalar
- `neighbor_{up,down,left,right}_empty`
- `alone_in_row`, `alone_in_col`

**Sahne geneli**
- `n_objects_lt_T` — T ∈ {2, 4, 8, 16}
- `exists_cluster_c`
- `two_same_cluster_adjacent`

Toplam ~200-400 yüklem beklenir. Bu Z3 için rahat bir boyut.

`predicates.py` şu arayüzü sunsun:

```python
def predicate_names() -> list[str]: ...
def encode(state, action, focus_obj=None) -> list[bool]:  # sabit uzunlukta
```

### 2.3 Gözlem tablosu

`env.py` ile keşif koştur, her adımda kaydet:

```python
{"p": [bool,...],        # encode() çıktısı
 "effect": int,          # transition.py etki kodu
 "action": int}
```

Hedef etki `E` için:
- **POZİTİF** = E'nin gerçekleştiği gözlemler
- **NEGATİF** = E'nin gerçekleşmediği gözlemler

### 2.4 Kodlama (matematik — birebir uygula)

`b_j ∈ Bool`, j = 1..N: *"j. yüklem koşulda VAR"*.

Kural `i` gözleminde ateşler ⟺ `∀j: b_j → p_i[j]`

**Adım A — aday kümesini daralt.**
Kural tüm pozitifleri kapsamak zorunda olduğundan, sadece **tüm pozitiflerde doğru olan**
yüklemler kullanılabilir:

```
J = { j : p_i[j] = 1,  her pozitif i için }
```

Bu tek satır arama uzayını genelde 10 kat düşürür. Atlama.

**Adım B — her negatif için bir clause.**
Kural negatifte ateşlememeli, yani en az bir seçili yüklem orada yanlış olmalı:

```
her negatif i için:   OR_{ j ∈ J,  p_i[j] = 0 }  b_j
```

**Adım C — amaç.**

```
minimize  Σ_{j ∈ J} b_j
```

Bu bir **minimum set cover** problemi. NP-zor ama MaxSAT çözücüler bunu rutin olarak yer.
Çıkan `b` vektörü = veriyle tutarlı **en kısa** kural. Occam/MDL burada sonradan uygulanan
bir filtre değil, doğrudan amaç fonksiyonu.

### 2.5 İskelet (`denme/solver/learn.py`)

```python
from z3 import Optimize, Bool, Or, If, sat

def learn_rule(positives, negatives, pred_names, timeout_ms=5000):
    N = len(pred_names)
    J = [j for j in range(N) if all(p[j] for p in positives)]
    if not J:
        return None, "no_candidate_predicates"

    b = {j: Bool(f"b_{j}") for j in J}
    o = Optimize()
    o.set("timeout", timeout_ms)

    for p in negatives:
        lits = [b[j] for j in J if not p[j]]
        if not lits:
            return None, "unseparable"      # ← ÖNEMLİ: havuz yetersiz, logla
        o.add(Or(lits))

    o.minimize(sum(If(b[j], 1, 0) for j in J))

    if o.check() != sat:
        return None, "unsat"
    m = o.model()
    return [j for j in J if m.evaluate(b[j])], "ok"
```

**`unseparable` durumunu mutlaka logla.** Bu "yüklem havuzum bu ayrımı ifade edemiyor"
demektir ve hangi yüklemi eklemen gerektiğini söyleyen en değerli sinyaldir.

### 2.6 FAZ 1 kabul kriteri

`vc33` oyununda (zaten seviye 2'ye çıkılan oyun):
- Gözlemlerin %80'iyle kural öğren, kalan %20'de test et
- **Geçer:** tutulan gözlemlerde ≥%80 doğru tahmin, kural uzunluğu ≤ 5 yüklem
- Çözüm süresi tek kural için < 5 sn

Kriter tutmadan FAZ 2'ye geçme.

---

## 3. FAZ 2 — CEGIS ile deney seçimi

Asıl kazanç burada. FAZ 1 kuralı öğreniyor; FAZ 2 **hangi aksiyonu harcayacağına** karar veriyor.

### 3.1 İkinci hipotezi bul

`b*` optimal çözüm, maliyeti `c`. Aynı problemi tekrar çöz ama engelleme clause'u ekle:

```
OR_{ j : b*_j = 1 }  ¬b_j        # seçilenlerden en az biri düşmeli
```

ve `Σ b_j ≤ c + 1` kısıtı koy. Çıkan `b²` = neredeyse aynı sadelikte **ikinci** hipotez.

İkisi de veriyle tutarlı. Yani hangisinin doğru olduğunu **bilmiyorsun**. Bilmek için deney lazım.

### 3.2 Ayırt edici aksiyonu bul

Mevcut durumdan `env.candidates()` ile gelen her aday aksiyon `a` için:

```python
r1 = rule_fires(b_star, encode(state, a))
r2 = rule_fires(b_two,  encode(state, a))
if r1 != r2:
    ayirt_edici_adaylar.append(a)
```

`r1 != r2` olan bir aksiyon varsa **onu oyna**. Sonuç ne olursa olsun iki hipotezden
birini kesin öldürür.

Yoksa: Go-Explore arşivindeki durumlara bak, hangisinde ayrım oluşuyorsa oraya git.
(Arşiv zaten `strategies.py` içinde var, yeniden yazma.)

### 3.3 Döngü

```
1. Gözlemlerle en kısa kuralı çöz            → R1
2. İkinci en kısa tutarlı kuralı çöz         → R2
3. R2 yoksa → kural tekil, GÜVEN. Plana geç.
4. R1 ve R2'nin ayrıldığı aksiyonu bul       → a*
5. a* oyna, sonucu gözlem havuzuna ekle
6. 1'e dön
```

Her tur hipotez uzayının en az yarısını öldürür. Aksiyon bütçesinin bilgi-teorik olarak
verimli kullanımı budur.

### 3.4 FAZ 2 kabul kriteri

`vc33`, `tn36`, `r11l`, `cd82` üzerinde:
- **Seviye 1'e ulaşmak için gereken aksiyon sayısı**, `I_wrong_elim_reward` temeline göre
  ölçülsün
- **Geçer:** en az 2 oyunda aksiyon sayısı ≥%25 düşük, hiçbir oyunda seviye kaybı yok

Sadece "geçiyor mu" değil, **kaç aksiyonda geçiyor** raporlansın. Skor formülü bu.

---

## 4. FAZ 3 — Makro besteleme (sadece FAZ 1+2 geçerse)

21 oyunun tosladığı duvar: "seç → hedef → uygula" gibi çok adımlı diziler.

**Önce basit olanı dene:** öğrenilen kurallar üzerinde derinlik 3-4 BFS. Kurallar
elindeyse çoğu makro böyle bulunur ve bu bir öğleden sonralık iş.

BFS yetmezse SAT-planlama:
- Zaman adımı `t = 0..k`, her adım için aksiyon değişkenleri
- Öğrenilen kurallar geçiş aksiyomları olarak
- Frame aksiyomu: bir yüklem, onu değiştiren kural ateşlemedikçe sabit kalır
- Hedef: `t = k`'da hedef yüklemi doğru
- `k = 1`'den başla, `sat` çıkana kadar artır

Referans: Kautz & Selman, *planning as satisfiability*.

**Durum uzayını ham 64×64 grid olarak kodlama** — patlar. Nesne düzeyinde soyutla:
az sayıda nesne, her biri ayrık öznitelikli.

---

## 5. ENTEGRASYON — hangi katman ne yapar

```
algı + VSA   →  nesne, sahne, benzerlik, hızlı hafıza      (vektör: iyi olduğu iş)
SMT/CEGIS    →  geçiş kuralı + deney seçimi                 (mantık: vektörün yapamadığı)
BFS/SAT-plan →  makro besteleme
yanlış-eleme →  çözücü zaman aşımına uğrarsa YEDEK
```

VSA'yı **silme**. Nesne tanıma ve benzerlik için tut. Kural çıkarma ve planlama işini
çözücüye devret. Sebep: `unbind` her uygulamada gürültü ekler, zincirlendiğinde 3-4 adım
sonra sinyal kaybolur — bu ayar meselesi değil, yöntemin matematiksel sınırı.

---

## 6. KISITLAR

- **Zaman aşımı zorunlu.** Her Z3 çağrısında `timeout` ayarla (5 sn öneri). Zaman aşımında
  sessizce `I_wrong_elim_reward`'a düş. Ajan asla donmamalı.
- **9 saat toplam bütçe.** Oyun başına ~10 dk. Çözücü çağrısı sayısını sınırla; aynı gözlem
  kümesi için sonucu cache'le (gözlem havuzunun hash'i ile).
- **Offline.** Kaggle'da internet yok. z3 wheel'i önceden paketle.
- **Determinizm.** Tohum sabitle, sonuçlar tekrarlanabilir olsun.

---

## 7. YAPILMAYACAKLAR

- `agent/` klasörüne dokunma. Sadece `denme/solver/` altında çalış.
- Oyuna özel yüklem yazma (`lf52_is_cargo` gibi). Yüklemler oyun-nötr olmalı; aksi halde
  özel oyunlarda çöker.
- Public oyunlara bakarak eşik ayarlama. Her ayarlanan sabit bir aşırı-uyum riskidir; ayar
  yaptıysan `AYAR.md`'ye yaz.
- LLM çağrısı ekleme. Bu faz tamamen sembolik.

---

## 8. TESLİM

```
denme/solver/
├── predicates.py     yüklem havuzu + encode()
├── learn.py          MaxSAT kural öğrenme
├── cegis.py          ikinci hipotez + ayırt edici aksiyon + döngü
├── plan.py           BFS (ve gerekirse SAT-planlama)
├── agent.py          hepsini bağlayan ajan (yanlış-eleme yedekli)
├── test_solver.py    birim testler
└── SONUC.md          faz faz ölçüm sonuçları
```

`SONUC.md` şunları içermeli, oyun bazında:

| Oyun | Temel: aksiyon/seviye | Çözücü: aksiyon/seviye | Ulaşılan seviye | `unseparable` sayısı |
|---|---|---|---|---|

`unseparable` sütunu en değerli çıktı: yüklem havuzunun nerede yetersiz kaldığını gösterir.

---

## 9. SIRA

1. z3 kur, doğrula, offline wheel'i hazırla
2. `predicates.py` yaz, `vc33`'te encode() çıktısını gözle doğrula
3. `learn.py` yaz, FAZ 1 kabul kriterini ölç → **dur, raporla**
4. `cegis.py` yaz, FAZ 2 kabul kriterini ölç → **dur, raporla**
5. Ancak ikisi de geçtiyse FAZ 3

Her fazın sonunda dur ve ölçüm raporla. Beş şey birden inşa etme — hangi katmanın
işe yaradığını ölçemezsen körlemesine ilerlemiş olursun.
