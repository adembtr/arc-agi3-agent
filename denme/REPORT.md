# DENEME — 13 Keşif/Karar Yöntemi Karşılaştırması

> Amaç: saf **matematik/olasılık/fizik** ile (LLM YOK, insan-izi YOK, önceden-eğitilmiş
> model YOK) ilk galibiyet bariyerini aşacak en iyi yöntemi bulmak.
> Orijinal `agent/` mimarisine DOKUNULMADI — her şey `denme/` altında, kopya altyapıyla.

## Kurulum
- Altyapı: `infra/` (perception, action, transition — sıfırdan-sembolik, kopya).
- `env.py`: hızlı headless ortam (HTTP/UI yok, ~150 adım/sn).
- `bench.py`: metrikler. `strategies.py`: 13 yöntem. `run_all.py`: karşılaştırma.
- Koşu: 1500 adım × 2 tekrar × 3 oyun (lf52 click, m0r0 kb-click, ft09 none).

## Metrikler (hepsi proxy — hiçbiri seviye geçmediği için ayırt edici)
- `max_level`: ulaşılan seviye (asıl hedef)
- `coverage`: görülen farklı durum sayısı (keşif genişliği)
- `events`: keşfedilen farklı olay-token (mekanik öğrenme)
- `merges`: birleşme olayı (kritik mekanik)
- `goal_drop`: nesne sayısında en büyük düşüş (hedefe yaklaşma)

## SONUÇ — Sıralama (1500 adım)

| # | Yöntem | Skor | Kapsam | Olay | Birleşme | Hedef |
|---|--------|------|--------|------|----------|-------|
| 1 | **13_go_explore** | **42.9** | 304 | 78 | 0 | 2.0 |
| 2 | 10_novelty_search | 40.3 | 183 | 72 | 0 | 2.0 |
| 3 | 08_thompson | 39.6 | 187 | 70 | 0 | 3.0 |
| 4 | 11_belief_infogain | 39.2 | 192 | 68 | 0 | 3.0 |
| 5 | 01_random | 37.9 | 182 | 66 | 0 | 3.0 |
| 6 | 03_novelty | 37.8 | 178 | 66 | 0 | 3.0 |
| 7 | 02_count_ucb | 19.4 | 172 | 31 | 0 | 1.0 |
| 8 | 06_max_entropy | 19.4 | 172 | 31 | 0 | 1.0 |
| 9 | 09_goal_greedy | 19.4 | 172 | 31 | 0 | 1.0 |
| 10 | 04_efe | 13.7 | 130 | 18 | 0 | 1.0 |
| 11 | 05_curiosity | 13.7 | 130 | 18 | 0 | 1.0 |
| 12 | 07_empowerment | 13.7 | 130 | 18 | 0 | 1.0 |
| 13 | 12_model_plan | 13.7 | 130 | 18 | 0 | 1.0 |

## SEÇİLEN YÖNTEM: **Go-Explore** (13)

**Neden:**
- **En yüksek keşif genişliği** (kapsam 304, olay 78) — özellikle m0r0'da 214 farklı durum.
- **Reset-only ortamımıza doğal uyum:** "arşivle + umut veren duruma reset+replay ile dön +
  oradan keşfet." Bizim geri-izleme/replay mekanizmamızla birebir örtüşür.
- Seyrek-ödüllü sert-keşif oyunlarının klasik en güçlü saf-algoritması (Montezuma'yı çözen).
- m0r0'da **min_obj=2**'ye indi — nesne sayısını en çok azaltan (hedefe en çok yaklaşan).

## DÜRÜST GERÇEK — hiçbiri seviye geçemedi

**13 yöntemin HİÇBİRİ hiçbir oyunda seviye 1'i geçemedi (max_level=0), ve HİÇ birleşme
üretemedi (merges=0).** 1500 adımda bile.

### Asıl darboğaz keşif bonusu DEĞİL — MAKRO/DİZİ keşfi
En net bulgu: açgözlü sömürü yöntemleri (efe/curiosity/empowerment/model_plan) **en kötü**
(kapsam 130) — ödül sinyali yokken çöküp tekrara giriyorlar. Keşif-ağırlıklı yöntemler
(go_explore/novelty/thompson/random) daha iyi kapsıyor. Ama **hiçbiri "seç→hedef→uygula"
2-adımlı birleştirmeyi tetikleyemiyor** — çünkü bu, tek aksiyon değil **koordineli aksiyon
ÇİFTİ** gerektiriyor, ve tek-adım keşif bunu zincirlemiyor.

**Ders:** Sorun "hangi keşif bonusu" değil. Ajanın **tek aksiyon değil, aksiyon DİZİSİ/makro**
keşfetmesi gerekiyor. Go-Explore'un üstünlüğü (durumu hatırla + oraya dön) doğru yön — çünkü
bulunan durumların ÜSTÜNE inşa edebiliyor. Eksik olan: arşivlenen durumdan **aksiyon
ÇİFTLERİNİ** sistematik denemek.

## UZUN BÜTÇE TESTİ (5000 adım, en iyi 3) — kritik kanıt

| Yöntem | Oyun | Kapsam | min_obj | Birleşme | Seviye |
|--------|------|--------|---------|----------|--------|
| go_explore | m0r0 | **477** | **2** | 0 | 0 |
| go_explore | lf52 | 162 | 56 | 0 | 0 |
| novelty_search | m0r0 | 101 | 2 | 0 | 0 |
| thompson | m0r0 | 107 | 2 | 0 | 0 |

**İki çarpıcı bulgu:**
1. **Go-Explore keşifte açık ara önde** (m0r0'da 477 vs ~100 = ~4.5 kat). Seçim doğru.
2. **AMA 5000 adımda bile hiç birleşme / hiç seviye yok.** Ve **TÜM yöntemler m0r0'da
   min_obj=2'ye iniyor** — yani "2 nesne kaldı" noktasına herkes ulaşıyor, ama **son iki
   nesneyi BİRLEŞTİREMİYOR.**

**Bu kesin kanıt:** Duvar keşif genişliği değil. Herkes hedefin eşiğine (2 nesne) geliyor
ama son **koordineli birleştirme aksiyonunu** bulamıyor. Go-Explore 4.5 kat daha çok keşfetse
de bu tek adımı yapamıyor → sorun **tek-aksiyon vs aksiyon-DİZİSİ**.

## ÖNERİ (kullanıcı döndüğünde)
1. **Go-Explore + makro keşfi**: arşivlenen her umut-verici durumdan **2-3 aksiyonluk
   diziler** dene (tek aksiyon değil). "Seç→hedef" çifti ancak böyle bulunur.
2. Go-Explore'un "hücre" tanımını kabalaştır (tam grid-fp yerine nesne-sayısı+kümeler) →
   anlamlı durumlar arşivlensin, gürültü değil.
3. ft09 (desen-eşleştirme) için özel: yön aksiyonu yok, sadece tık; hedef "şablon eşle" →
   goal-hipotezi diline **şablon-eşleştirme** eklenmeli (mevcut min_count/min_obj yetmiyor).

## Dosyalar
- `infra/` kopya altyapı · `env.py` · `bench.py` · `strategies.py` · `run_all.py`
- `SONUCLAR.json` tam metrikler · `best.py` seçilen yöntem (Go-Explore) izole

---

# KIRILMA — Yanlış-Eleme + Ödül (kullanıcının fikri) İLK KEZ SEVİYE GEÇTİ

## Fikir (kullanıcı)
Doğru cevap tek ve gizli → bulmak zor. Ama YANLIŞ bol ve hedefi bilmeden görülür
(etki-yok / geri-dönüş / game-over). "Tüm yanlışları ele, geriye doğru kalır."

## Mekanizma (I_wrong_elim_reward)
- **W[bağlam-token, aksiyon]** = 1'den başlar, SADECE yanlışta düşer (×0.15). Bayes eleme.
- Bağlam ZENGİN: (6, şekil-token) = tık ayrı, (n, -1) = tuş ayrı → tık/tuş/olay ayrı elenir.
- YANLIŞ (ele) = etki-yok / geri-dönüş / game-over. YANLIŞ DEĞİL = herhangi yapısal değişim
  (çok-adımlı doğru hamleyi korur).
- Yeni şekil → yeni token → W=1 (TAZE, elenmez). Seviye atlayınca eski elemelere 2. şans (×4 revive).
- Ödül: yeni durum (+0.3), seviye (+10, kredi). Go-Explore omurga (umut veren duruma reset+replay).
- Bağlam TOKEN → genelleşir. Her oyunda sıfırdan. EZBER YOK, ÖĞRENME YOK.

## SONUÇ — 25 oyun taraması (1800-3000 adım, 2 tohum)

**SEVİYE GEÇEN (4/25):**
- **vc33: seviye 2** (5/5 tohum güvenilir)
- **cd82: seviye 1**
- **tn36: seviye 1**
- **r11l: seviye 1**

**Geçemeyen (21/25):** lf52, m0r0, g50t, ft09, lp85, s5i5, su15, ar25, bp35, cn04,
dc22, ka59, sc25, sk48, sp80, tu93, sb26, re86, tr87, ls20, wa30.

## Analiz
- Geçen 4 oyun: **kısa tık-dizisiyle ilerleyen** tipler (tıkla→desen eşle / renk değiştir).
  Yanlış-eleme bunlarda doğru tıklamayı hızla buluyor.
- Geçemeyen 21: **uzun koordineli dizi** gerektiren tipler (kargoyu ray'de sür, çok-adımlı
  taşıma). Tek-adım yanlış-eleme bunları çözemiyor — makro/dizi problemi burada da duruyor.

## Değerlendirme
- Bu, TÜM oturumun **ilk seviye-geçen** yöntemi. Kullanıcının "yanlıştan öğren" fikri işe yaradı.
- 4/25 = %16 oyun seviye 1+ (biri seviye 2), saf sıfırdan-sembolik, ezbersiz.
- Sonraki adım: geçemeyen 21 için **makro (2-3 aksiyonluk dizi) yanlış-elemesi** — tek aksiyon
  değil, DİZİ elemek/canlı tutmak. Uzun-dizi oyunları ancak böyle açılır.

## Canlı izleme
`live.py` -> http://localhost:8005 (SPACE ile adım; W ağırlıkları, elenen aksiyonlar,
ödül kredisi canlı). Kazanan yöntem: I_wrong_elim_reward.
