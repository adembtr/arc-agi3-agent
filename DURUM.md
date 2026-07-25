# DURUM.md — ARC-AGI-3 ajanı: tam durum özeti (2026-07-25)

> **Bu dosya sıfırdan okunmak için yazıldı.** Projeye yeni giren biri (veya yeni bir
> Claude oturumu) sadece bunu okuyarak nerede olduğumuzu, neyin çalıştığını, neyin
> çalışmadığını ve sıradaki tek işi anlayabilir. Detaylar için: `plan.md` (vizyon +
> tokenizer mimarisi), `SONUC.md` (solver ölçümleri), `denme/goal/SONUC2.md` (hedef
> görevi ölçümleri), `denme/solver/AYAR.md` (elle ayarlanan her sabitin gerekçesi).

---

## 1. PROJE NEDİR

**ARC-AGI-3 Kaggle yarışması** için **sıfırdan-sembolik ajan.**
- Girdi: her adım 64×64 tamsayı grid (renkler 0–15). Çıkış: 1 aksiyon.
- Aksiyonlar: `0`=RESET (evrensel), `6`=CLICK(x,y) (evrensel); `1-5,7`=oyuna özel tuşlar
  (anlamı denemeyle keşfedilir).
- Her oyun bir bulmaca; ajan **her oyunda hafızayı sıfırlar** ve oyun içinde öğrenir.
- Test oyunları GİZLİ ve YENİ → ezber işe yaramaz; oyunlar-arası tekrar eden **mekaniği**
  yakalamak gerekir.

### DEĞİŞMEZ KISITLAR (kullanıcının)
- **LLM YOK · insan-izi/hareket-takibi YOK · önceden-eğitilmiş model YOK · EZBER YOK.**
- Her şey emergent NUMARA (token) olmalı — "yeşil", "duvar", "kargo" gibi insan etiketi
  YOK. Şekil/rol/olay/hedef hep sayıdan hesaplanır (frekans, geometri, şekil imzası).
- Felsefe: **"doğruyu bulma (tek, gizli, zor); YANLIŞI ele (bol, görünür)."**
- Kök dizin: `/home/adem/Desktop/AGI/` · GitHub: github.com/adembtr/arc-agi3-agent

---

## 2. NE ÇALIŞIYOR (kanıtlanmış)

### 2.1. Tek seviye-geçen yöntem: **I_wrong_elim_reward** (yanlış-eleme)
`denme/strategies2.py`. **4/25 oyunda seviye geçti** (vc33 sv2; cd82, tn36, r11l sv1).
W[bağlam-token, aksiyon]=1'den başlar, SADECE yanlışta düşer (×0.15): etki-yok /
geri-dönüş / game-over. Bağlam token → genelleşir. Go-Explore omurga + ödül kredisi.
**Tüm oturumun ilk ve HÂLÂ en iyi seviye-geçen yöntemi.**

### 2.2. Temsil katmanı (agent/ + denme/infra/) — sağlam
- **Şekil tokenizer** (perception.py): grid → bağlı-bileşen nesne, ölçek/ayna-bağımsız
  imza, prototip küme, bileşik şekiller.
- **Olay tokenizer** (transition.py): sayısal etki kodları (MOVE/MERGE/APPEAR/…),
  kümegeçişi token'ı — insan etiketi yok.
- **Rol tokenizer** (RoleModel): davranış vektöründen emergent rol (arka-plan/sayaç 3
  oyunda etiketsiz bulundu).

### 2.3. SMT/MaxSAT kural öğrenme (denme/solver/) — ✅ FAZ 1 GEÇTİ
`predicates.py` (192 oyun-nötr yüklem) + `learn.py` (Z3 MaxSAT). vc33'te 6/6 etki için
en-kısa kural, doğruluk 0.84–0.98, <0.2sn. **Ders:** tek VE-kuralı yetmez (mekanik AYRIK)
→ kural LİSTESİ (DNF) + polarite şart. `unseparable` = en değerli teşhis sinyali.

### 2.4. Hedef hipotezi (denme/goal/goals.py) — ✅ MODÜL A 4/4
İlk kareden, **aksiyon harcamadan**, saf geometriden 5 şablon:
UNIFY/FIT/OVERLAP/CONSISTENT/COLLECT. İnsan hedefiyle eşleşme: m0r0→UNIFY, g50t→FIT,
ar25→OVERLAP, lf52→COLLECT. **"Dünya bilgisi olmadan sayıyla hedef" kanıtlandı.**

### 2.5. Meta tespit (denme/goal/meta.py) — ✅ MODÜL B 4/4
Sayaç (aksiyondan bağımsız monoton) / tehlike (geri-sarma ≥2 gözlem) / bağlaşık (aynı
yer-değiştirme ≥2 nesne). ft09 sayaç, g50t A5-tehlike, ar25 coupled — hepsi doğru.

### 2.6. φ (renk-eşleme) çıkarımı (denme/goal/schema.py) — çekirdek ✅
ft09'da CONSISTENT şeması + **φ={0→8, 2→9}** = insan notundaki eşlemeyle BİREBİR,
aksiyonsuz, sadece çoğunluk-tutarlılığından.

### 2.7. Bisimülasyon (denme/solver/bisim.py) — umut verici
0.22 görünüm-eşiği yerine davranışsal denklik: tn36 %63, r11l %83 daha az aksiyon.
Ama vc33 sv2 kaybı (gizli-durumda davranış imzası yanıltıcı). Uyarlanır kip = açık iş.

---

## 3. NE ÇALIŞMIYOR (dürüst)

### TEK GERÇEK DUVAR: **PLANLAYICI (koordineli çok-adımlı arama)**

| Deneme | Sonuç |
|---|---|
| 20+ keşif/karar yöntemi (denme/strategies*.py) | Hiçbiri makro-dizi oyunlarını geçemedi |
| VSA/TPR beyni (tek-atış kural) | 2/4 kıyas; unbind zincirde gürültü → sınır |
| CEGIS deney seçimi (solver FAZ 2) | 0/4 kazanç → sv1-öncesi sömürülecek kural yok |
| Hedef-güdümlü ajan (goal FAZ) | 0/5 yeni oyunda sv1 |

**Neden:** Uzun koordineli aksiyon dizisi gerektiren oyunlar (21/25) tek-adım
keşif/tırmanışla çözülmüyor. Örnek (ar25): OVERLAP progress 0.10'a çıkıp platoya
giriyor — yatay mesafe kapanıyor, dikey kalıyor; ajan "plato → farklı aksiyona geç →
geri-dönüşü yönet" dinamiğini bulamıyor. Model-free tepe-tırmanışının matematiksel
sınırı bu.

**AMA kritik ilerleme:** darboğaz artık "hedefi/kuralı bilmemek" DEĞİL. Perception +
şekil + olay + rol + **hedef (A)** + **meta (B)** + **kural-öğrenme (solver FAZ 1)**
hepsi ÇALIŞIYOR. Eksik olan TEK katman: bunların üstünde gerçek **arama**.

---

## 4. SIRADAKİ TEK İŞ — PLANLAYICI

Girdiler HAZIR:
- Öğrenilmiş geçiş kuralları (solver FAZ 1: `(aksiyon, koşul) → etki`, 0.84–0.98 doğru).
- İlk-kare hedefi + progress sezgiseli (goal Modül A).
- Tehlike/bağlaşık/sayaç meta-bilgisi (goal Modül B).
- φ renk-eşlemesi (goal Modül C).

Yapılacak: bunların üstünde **çok-adımlı arama**:
1. **Basit:** öğrenilen kurallar üstünde derinlik 3-4 BFS/A* (sezgisel = hedef progress).
   Durum = NESNE-düzeyi soyutlama (ham 64×64 DEĞİL — patlar).
2. **Yetmezse:** SAT-planlama (Kautz & Selman) — zaman-adımlı aksiyon değişkenleri +
   kural geçiş aksiyomları + frame aksiyomu; k=1'den sat çıkana kadar.
3. **Makro:** bağlaşık nesneler için "duvara-daya sonra ayrıştır" (m0r0 çözüm anahtarı);
   coupled tespiti (Modül B) bu makroyu tetiklemeli.

İkincil işler: uyarlanır bisimülasyon (determinizme göre kip); VSA eleme dengesi.

---

## 5. DİZİN HARİTASI

```
/home/adem/Desktop/AGI/
├── DURUM.md              ← BU DOSYA (sıfırdan tam özet)
├── plan.md               vizyon + tokenizer mimarisi + §18 solver + §19 hedef
├── SONUC.md              solver ölçümleri + EK: hedef görevi özeti
├── solver_gorev.md       SMT/CEGIS şartnamesi (tamamlandı)
├── hedef_gorev.md        hedef/meta/şema şartnamesi (tamamlandı)
├── agent/                ORİJİNAL mimari (perception/transition/brain_ui) — canlı UI'lar
├── player/               insan oyun aracı + notes/*.txt (5 oyun insan izi = DSL spec)
├── environment_files/    25 oyun (.gitignore'da)
├── solver_wheels/        z3 offline wheel (.gitignore'da)
└── denme/                DENEY klasörü (orijinale dokunmadan; kopya infra/)
    ├── strategies2.py    I_wrong_elim_reward = KAZANAN (4/25 sv)
    ├── vsa.py/knowledge.py/vsa_agent.py   VSA/TPR beyni
    ├── solver/           SMT görevi: predicates/learn/cegis/bisim/plan/agent
    │   ├── SONUC.md  AYAR.md  test_solver.py (17/17)
    ├── goal/             hedef görevi: goals/meta/schema/goal_agent
    │   └── SONUC2.md      A 4/4 · B 4/4 · C çekirdek✅ · entegrasyon 0/5
    └── env.py bench.py    hızlı headless ortam + metrikler
```

## 6. ÇALIŞTIRMA
```bash
cd /home/adem/Desktop/AGI/denme
uv run --project ../ARC-AGI-3-Agents python goal/goals.py     # Modül A kabul
uv run --project ../ARC-AGI-3-Agents python goal/meta.py 1200 # Modül B kabul
uv run --project ../ARC-AGI-3-Agents python solver/learn.py vc33 1500  # FAZ 1
uv run --project ../ARC-AGI-3-Agents python solver/test_solver.py      # 17/17
```
OPERATION_MODE=offline otomatik. z3: `uv pip install z3-solver` (veya solver_wheels/).

## 7. TEK CÜMLE
Perception→hedef→kural katmanlarının hepsi çalışıyor ve etiketsiz/sayısal; seviye geçen
tek yöntem hâlâ yanlış-eleme (4/25); **tosladığımız tek duvar planlayıcı** ve onun tüm
girdileri (öğrenilmiş kural + ilk-kare hedefi) artık hazır.
