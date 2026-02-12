# 🎬 YouTube Shorts AI Video Generator

**Tam otomatik, kendi kendini öğrenen YouTube Shorts video üretim sistemi**

Tarihsel içerikler için AI destekli video üretimi yapar. Senaryo yazımından video render'ına, kalite skorlamasından YouTube Analytics takibine kadar tüm süreç otomatiktir. **Thompson Sampling** tabanlı autopilot sistemi ile parametreler gerçek YouTube performansına göre sürekli optimize edilir.

### 🆕 Son Güncellemeler (v2.0 - Media Mogul)
- **🎯 History Buffet**: 6 kategorili akıllı konu seçim stratejisi (Forced Diversity)
- **📊 Virality Score**: Retention × 1.5 + Stopping Power × 2.0 (Like'lar artık yok sayılıyor)
- **🎬 Visual Director**: 4 katmanlı sinematik prompt sistemi (Global Style → Era → Action → Mood)
- **🌍 Antropoloji & Kültür**: Yeni kategori — Aztek Ölüm Düdüğü, Tibet Gökyüzü Cenazesi, Viking Blood Eagle
- **🧠 Kategori Feedback Loop**: Başarılı kategorilerin ağırlığı otomatik artırılır

---

## 📋 İçindekiler

1. [Sistem Genel Bakış](#-sistem-genel-bakış)
2. [Nasıl Çalışır?](#-nasıl-çalışır)
3. [Konu Seçim Stratejisi (History Buffet)](#-konu-seçim-stratejisi-history-buffet)
4. [Virality Score (Performans Puanlama)](#-virality-score-performans-puanlama)
5. [Senaryo Üretimi ve Puanlama](#-senaryo-üretimi-ve-puanlama)
6. [Görsel Üretimi (Visual Director)](#-görsel-üretimi-visual-director)
7. [Ses Üretimi (AWS Polly)](#-ses-üretimi-aws-polly)
8. [Müzik Sistemi](#-müzik-sistemi)
9. [Video Kompozisyonu (FFmpeg)](#-video-kompozisyonu-ffmpeg)
10. [Autopilot Sistemi](#-autopilot-sistemi)
11. [YouTube Analytics Entegrasyonu](#-youtube-analytics-entegrasyonu)
12. [İş Takibi (Job Tracking)](#-iş-takibi-job-tracking)
13. [Admin Paneli](#-admin-paneli)
14. [AWS Altyapısı](#-aws-altyapısı)
15. [Kurulum](#-kurulum)
16. [Dosya Yapısı](#-dosya-yapısı)
17. [Konfigürasyon](#-konfigürasyon)
18. [Sorun Giderme](#-sorun-giderme)

---

## 🌟 Sistem Genel Bakış

Bu sistem tamamen **serverless** (sunucusuz) bir mimaride çalışır:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            AWS Cloud                                    │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│           Video Generator Lambda             │   │
│  │  (Scheduler) │    │  • Senaryo üret (Claude)                     │   │
│  │  Her 8 saat  │    │  • Görsel üret (Titan)                       │   │
│  └──────────────┘    │  • Ses üret (Polly)                          │   │
│                      │  • Video birleştir (FFmpeg)                   │   │
│  ┌──────────────┐    │  • Autopilot config'e göre parametre seç     │   │
│  │  API Gateway │───▶│  • Job tracking & structured logging         │   │
│  │ POST /generate│   └──────────────┬───────────────────────────────┘   │
│  └──────────────┘                   │                                   │
│                                     ▼                                   │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │      S3      │◀───│         Video & Metadata & Logs              │   │
│  │   (Storage)  │    └──────────────────────────────────────────────┘   │
│  └──────────────┘                                                       │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│         Analytics Fetcher Lambda              │   │
│  │  (23:00 UTC) │    │  • YouTube'dan gerçek retention çek          │   │
│  └──────────────┘    │  • Tahminlerle karşılaştır                   │   │
│                      └──────────────┬───────────────────────────────┘   │
│                                     │                                   │
│                                     ▼                                   │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│         Decision Engine Lambda                │   │
│  │  (23:30 UTC) │    │  • Thompson Sampling ile ağırlık güncelle    │   │
│  └──────────────┘    │  • Recovery mode kontrolü                    │   │
│                      └──────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│         Prompt Memory Lambda                  │   │
│  │  (Pazar 21:00)│   │  • Top/bottom 5 video'dan DO/DON'T çıkar    │   │
│  └──────────────┘    └──────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│         Weekly Report Lambda                   │   │
│  │  (Pazar 20:00)│   │  • Haftalık performans raporu gönder         │   │
│  └──────────────┘    └──────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │   DynamoDB   │◀───│  • shorts_video_metrics (video verileri)     │   │
│  │  (Database)  │    │  • shorts_jobs (iş takibi)                   │   │
│  └──────────────┘    │  • shorts_run_logs (yapısal loglar)          │   │
│                      │  • shorts_rate_limits (API rate limit)        │   │
│                      └──────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │ API Gateway  │───▶│            Admin API Lambda                   │   │
│  │  (REST API)  │    │  • Video CRUD + YouTube link                  │   │
│  └──────────────┘    │  • POST /generate + job tracking              │   │
│                      │  • Rate limiting + idempotency                │   │
│  ┌──────────────┐    └──────────────────────────────────────────────┘   │
│  │ CloudFront   │                                                       │
│  │ + S3 Static  │───▶ Admin Panel (HTML/JS/CSS)                        │
│  └──────────────┘                                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Nasıl Çalışır?

### Video Üretim Akışı (Adım Adım)

```
1. BAŞLA
   │
   ▼
2. AUTOPILOT CONFIG YÜKLE
   │  • Mode seç (QUALITY/FAST - ağırlıklı rastgele)
   │  • Hook ailesi seç (contradiction/shock/mystery/...)
   │  • Başlık varyantı seç (bold/safe/experimental)
   │
   ▼
3. KONU SEÇ (History Buffet stratejisi)
   │  • 6 kategoriden ağırlıklı rastgele seçim
   │  • Forced Diversity: Son kategori tekrar seçilemez
   │  • Similarity dampener ile tekrar kontrolü
   │
   ▼
4. SENARYO YAZDIR (Claude AI)
   │
   ├─▶ Hook yaz (ilk cümle - dikkat çekici)
   │   └─▶ Puan < 9.0 ise yeniden yaz (max 5 deneme)
   │
   ├─▶ Context yaz (bağlam - 2-3 cümle)
   │   └─▶ Puan < 8.5 ise yeniden yaz (max 3 deneme)
   │
   ├─▶ Body yaz (ana hikaye)
   │   └─▶ Puan < 8.5 ise yeniden yaz (max 3 deneme)
   │
   └─▶ Outro yaz (kapanış)
       └─▶ Puan < 8.5 ise yeniden yaz (max 3 deneme)
   │
   ▼
5. KPI TAHMİN ET
   │  • Instant Clarity (hemen anlaşılıyor mu?)
   │  • Curiosity Gap (merak uyandırıyor mu?)
   │  • Swipe Risk (kaydırma riski)
   │  • Predicted Retention (tahmini izlenme %)
   │
   ▼
6. GÖRSEL ÜRET (4 adet AI görsel - Titan)
   │  • Her segment için ayrı görsel
   │  • Ken Burns efekti (zoom/pan)
   │  • Tarihe uygun film grain
   │
   ▼
7. SESLENDİRME ÜRET (AWS Polly)
   │  • Belgesel tarzı erkek ses
   │  • Türkçe/yabancı isimleri fonetik yaz
   │
   ▼
8. MÜZİK SEÇ ve KES
   │  • Mood'a uygun müzik (epic, emotional, etc.)
   │  • En iyi segmenti bul ve kes
   │
   ▼
9. FFmpeg ile BİRLEŞTİR
   │  • 1080x1920 (9:16 vertical)
   │  • Altyazı ekle
   │  • Ses + müzik + SFX miksle
   │  • Film grain efekti
   │
   ▼
10. S3'e YÜKLE + DynamoDB'ye KAYDET
    │  • Video metrikleri → shorts_video_metrics
    │  • Job durumu → shorts_jobs
    │  • Yapısal loglar → shorts_run_logs
    │
    ▼
11. SNS ile BİLDİRİM GÖNDER
    │
    ▼
12. BİTTİ! ✅
```

---

## 🎯 Konu Seçim Stratejisi (History Buffet)

### Dosya: `lambda/video_creator/topic_selector.py`

Sistem artık rastgele konu seçmek yerine **stratejik bir içerik portföyü** yönetir. 6 kategoride 40+ konu arasından ağırlıklı seçim yapılır.

### Kategori Dağılımı

| Kategori | Ağırlık | Örnek Konular |
|----------|---------|---------------|
| 🔫 Modern Savaş | **30%** | Ghost Army, White Death, Manhattan Project |
| 🏛️ Antik Çağ | **25%** | Spartalılar, Sezar'ın intikamı, Mansa Musa |
| ⚔️ Ortaçağ | **20%** | Samurai vs Şövalye, Paris kuşatması, Cengiz Han |
| 🔍 Gizem | **15%** | Korsan Kralı, Karıncalanma Vebası, Alcatraz |
| 👑 Liderler | **10%** | Napoleon, Fatih Sultan Mehmet, İskender |
| 🌍 Antropoloji & Kültür | **10%** | Aztek Ölüm Düdüğü, Tibet Gökyüzü Cenazesi, Viking Blood Eagle |

### Forced Diversity (Zorunlu Çeşitlilik)

```
Son video: "Simo Häyhä" (modern_war)
     │
     ▼
Sonraki seçim: modern_war HARİÇ tüm kategorilerden ağırlıklı seçim
     │
     ▼
Seçilen: "Aztek Ölüm Düdüğü" (anthropology_and_culture) ✅
```

- **Aynı kategori asla arka arkaya gelmez**
- Benzer konular `similarity_dampener` ile filtrelenir
- Kategori ağırlıkları autopilot tarafından otomatik güncellenir

### Antropoloji & Kültür Kategorisi 🌍

Yüksek viral potansiyelli "insanlık hikayeleri"ne odaklanır:

| Konu | Dönem | Neden Viral? |
|------|-------|--------------|
| Aztek Ölüm Düdüğü | Antik | Ses efekti + korku |
| Tibet Gökyüzü Cenazesi | Modern | Şok + kültürel farklılık |
| Sokushinbutsu (Öz-Mumyalama) | Ortaçağ | "İmkansız" insan iradesi |
| Maori Haka Dansı | Modern | Güç + kültürel anlam |
| Viking Blood Eagle | Ortaçağ | Karanlık tarih + tartışma |

---

## 📊 Virality Score (Performans Puanlama)

### Dosya: `lambda/video_creator/utils/analytics_score.py`

Geleneksel "Like sayısı" metriği artık **tamamen yok sayılır**. Yerine, YouTube algoritmasının gerçekten önemsediği iki metrik kullanılır:

### Formül

```
Virality Score = (Retention × 1.5 + Stopping Power × 2.0) × log₁₀(Views)
```

| Bileşen | Açıklama | Ağırlık |
|---------|----------|---------|
| **Retention** | Ortalama izlenme yüzdesi (%) | ×1.5 |
| **Stopping Power** | `(1.0 - Swipe Rate) × 100` | ×2.0 |
| **Volume** | `log₁₀(Views)` — hacim çarpanı | ×1.0 |

> **Not:** Minimum 100 view gerekir. Altındaki videolar 0 puan alır.

### Örnek Hesaplamalar

| Video Tipi | Retention | Swipe Rate | Views | Skor |
|------------|-----------|------------|-------|------|
| 🔥 Viral Hit | %80 | %30 | 10,000 | **~1,040** |
| 💎 Niche Gem | %95 | %10 | 1,000 | **~700** |
| 💀 Clickbait | %30 | %60 | 50,000 | **~587** |

### Neden Like'ları Yok Sayıyoruz?

- Like **pasif** — kullanıcı zaten izlemiş, "iyi" diyor ama algoritma umursamıyor
- Retention = videonun **gerçek gücü** — insanlar gerçekten izliyor mu?
- Stopping Power = hook'un **gerçek etkisi** — kaydırmayı durduruyor mu?

---

## 📝 Senaryo Üretimi ve Puanlama

### Dosya: `lambda/video_creator/script_pipeline.py`

Bu dosya sistemin kalbidir. Her senaryo parçası AI tarafından puanlanır ve **minimum 8 puan** alana kadar yeniden yazılır.

### Puanlama Eşikleri

| Bölüm     | Minimum Puan | Max Deneme |
|-----------|--------------|------------|
| Hook      | 9.0          | 5          |
| Context   | 8.5          | 3          |
| Body      | 8.5          | 3          |
| Outro     | 8.5          | 3          |
| Final     | 8.5          | -          |

### Hook Nedir?

Hook, videonun **ilk 1-2 saniyesinde** söylenen cümledir. Seyircinin kaydırmamasını sağlar.

```
❌ Kötü Hook: "Bugün size Büyük Emu Savaşını anlatacağım."
✅ İyi Hook: "Avustralya kuşlara karşı savaş açtı ve kaybetti."
```

### Puanlama Sistemi Nasıl Çalışır?

1. **Claude AI** senaryo parçasını yazar
2. **Claude AI (Evaluator rolünde)** puanlar ve gerekçe yazar
3. Puan düşükse, evaluator'ın önerileriyle yeniden yazılır
4. Puan yeterli olana veya max deneme sayısına ulaşana kadar devam eder

```python
# script_pipeline.py'den örnek
HOOK_THRESHOLD = 9.0          # Hook en az 9 olmalı
SECTION_THRESHOLD = 8.5       # Diğer bölümler en az 8.5 olmalı
HOOK_MAX_ITERATIONS = 5       # Hook için max 5 deneme
SECTION_MAX_ITERATIONS = 3    # Diğer bölümler için max 3 deneme
```

### KPI Proxy Metrics

Gerçek YouTube performansını tahmin eden metrikler:

| Metrik            | Açıklama                                    | Aralık |
|-------------------|---------------------------------------------|--------|
| instant_clarity   | İlk saniyede ne olduğu anlaşılıyor mu?      | 0-10   |
| curiosity_gap     | "Sonra ne oldu?" merakı uyandırıyor mu?     | 0-10   |
| swipe_risk        | Kaydırma riski (yüksek = düşük risk)        | 0-10   |
| predicted_retention | Tahmini izlenme yüzdesi                   | 0-100  |

---

## 🎬 Görsel Üretimi (Visual Director)

### Dosya: `lambda/video_creator/stock_fetcher.py`

AWS Bedrock Titan Image Generator kullanarak **sinematik tarihsel görseller** üretir. v2.0 ile prompt'lar artık 4 katmanlı bir yapıda oluşturulur.

### 4 Katmanlı Prompt Mimarisi (Visual Director)

```
┌─────────────────────────────────────────────────┐
│ 1. GLOBAL STYLE (Görsel İmza)                   │
│    "cinematic historical illustration,           │
│     dark fantasy graphic novel art style"        │
├─────────────────────────────────────────────────┤
│ 2. ERA CONTEXT (Dönem Bağlamı)                  │
│    "15th century Ottoman period setting,         │
│     ornate armor, turbans, huge cannons"         │
├─────────────────────────────────────────────────┤
│ 3. SCENE ACTION (Sahne)                          │
│    "a scene showing young Ottoman sultan         │
│     commanding troops before fortress walls"     │
├─────────────────────────────────────────────────┤
│ 4. MOOD (Atmosfer)                               │
│    "dramatic lighting, volumetric fog,           │
│     tense atmosphere, cinematic shot"            │
└─────────────────────────────────────────────────┘
```

### Desteklenen Dönemler

| Dönem | Görsel DNA |
|-------|------------|
| Ottoman | Ornate armor, minarets, bombards |
| Roman | Legionary armor, marble columns |
| Viking | Longships, chainmail, foggy landscapes |
| Medieval | Knights, castles, heraldry banners |
| WW2 | 1940s gear, tanks, gritty war photography |
| Ancient | Stone temples, bronze weapons |
| Anthropology | Indigenous attire, ceremonial objects, National Geographic style |

### Güvenlik Filtresi (Titan Sanitizer)

AWS Titan bazı içerikleri engeller. **titan_sanitizer.py** prompt'ları güvenli hale getirir:

```python
# Örnek dönüşümler
"war" → "soldiers in marching formation"
"Genghis Khan" → "13th century Mongol emperor in golden armor"
"blood" → "crimson sunset"
```

**Yüz Kaçınma**: Tarihi figürlerin yüzleri yerine tanımlayıcı ifadeler kullanılır:
- `"Mehmed II"` → `"young Ottoman ruler in golden armor"`
- `"Napoleon"` → `"French military commander with bicorne hat"`

### Ken Burns Efekti + Fallback

- Her görsel **8 saniyelik** videoya dönüşür (zoom/pan/fade)
- Titan başarısız olursa: önceki başarılı görseli kullan veya gradient fallback oluştur

---

## 🎙️ Ses Üretimi (AWS Polly)

### Dosya: `lambda/video_creator/tts.py`

### Ses Karakteristikleri

| Özellik     | Değer                           |
|-------------|--------------------------------|
| Ses tipi    | Neural (doğal ses)              |
| Sesler      | Matthew, Brian, Stephen         |
| Hız         | 92-95% (biraz yavaş - dramatik) |
| Pitch       | -5% ile -10% (derin ses)        |

### Fonetik Yazım

Türkçe ve yabancı isimler İngilizce TTS'e zor gelir. Sistem bunları fonetik olarak yazar:

```python
PHONETIC_REPLACEMENTS = {
    "Atatürk": "Ah-tah-turk",
    "Mustafa Kemal": "Moos-tah-fah Keh-mahl",
    "Fatih": "Fah-teeh",
    "Constantinople": "Con-stan-tin-oh-pull",
    "Selahaddin": "Seh-lah-had-deen",
}
```

---

## 🎵 Müzik Sistemi

### Dosyalar:
- `lambda/video_creator/music_fetcher.py` - Müzik seçimi
- `lambda/video_creator/smart_music_cutter.py` - Akıllı kesim
- `lambda/video_creator/story_music_matcher.py` - Mood analizi

### Müzik Kategorileri

| Kategori     | Ne Zaman Kullanılır?           |
|--------------|--------------------------------|
| epic         | Savaş, fetih, imparatorluk     |
| emotional    | Kişisel hikayeler, trajedi      |
| documentary  | Genel tarihsel anlatım          |
| dramatic     | Gerilimli anlar                 |
| oriental     | Osmanlı, Arap, Asya hikayeleri  |

### Akıllı Kesim

Müzik dosyasının en iyi kısmını bulur:
1. Loudness analizi yapar
2. En yüksek enerji noktasını bulur
3. O noktadan gerekli süreyi keser
4. Fade-out ekler

---

## 🎬 Video Kompozisyonu (FFmpeg)

### Dosya: `lambda/video_creator/video_composer.py`

### Teknik Özellikler

| Özellik       | Değer           |
|---------------|-----------------|
| Çözünürlük    | 1080x1920 (9:16)|
| FPS           | 30              |
| Codec         | H.264 (libx264) |
| Preset        | fast            |

### Ses Karışımı

```
Voice:  100% volume (ana ses)
Music:   55% volume (arka plan)
SFX:     40% volume (ses efektleri)
```

### Dönemine Göre Efektler

| Dönem           | Efekt                                    |
|-----------------|------------------------------------------|
| Ancient/Medieval| Oil painting aesthetic, vignette         |
| 19th Century    | Sepia, light grain, vintage              |
| WW1/WW2         | Heavy film grain, black & white          |
| Modern          | Slight color fade, vintage film          |

---

## 🤖 Autopilot Sistemi

Sistem, gerçek YouTube performansını kullanarak kendi parametrelerini otomatik optimize eden **self-learning** bir yapıya sahiptir.

### Decision Engine

**Dosya:** `lambda/video_creator/decision_engine.py`
**Zamanlama:** Her gün 23:30 UTC (analytics fetcher'dan 30 dk sonra)

Thompson Sampling (Multi-Armed Bandit) algoritması ile şu parametrelerin ağırlıklarını otomatik günceller:

| Parametre       | Seçenekler                                   |
|-----------------|----------------------------------------------|
| Mode            | QUALITY (0.3-0.9), FAST (0.1-0.5)           |
| Title Variant   | bold, safe, experimental                      |
| Hook Family     | contradiction, shock, mystery, question, challenge, contrast |
| **🆕 Category** | modern_war, ancient, medieval, mystery, leaders, anthropology |

**Ağırlık güncelleme süreci:**
1. Tamamlanmış videoların **Virality Score**'unu hesapla
2. Reward hesapla (winsorization + decay weighting)
3. Beta distribution'ları güncelle (Thompson Sampling)
4. Softmax ile yeni ağırlıklar hesapla
5. Safety bounds uygula (günlük max %15 değişim)
6. 🆕 **Kategori ağırlıklarını güncelle** (Skor > 500 → Boost +5%, Skor < 250 → Nerf -5%)

**Decay Weights (eski veriye azalan ağırlık):**

| Video Yaşı | Ağırlık |
|------------|---------|
| 0-7 gün    | 1.0     |
| 8-14 gün   | 0.5     |
| 15-21 gün  | 0.25    |
| 22+ gün    | 0.1     |

**Guardrails:**
- **Recovery Mode:** Art arda 3 video retention < %25 ise otomatik QUALITY mode'a geçer
- Günlük max ağırlık değişimi: %15
- Safety bounds ile aşırı uçlara kayma engellenir
- 🆕 Kategori ağırlıkları her zaman toplamda 1.0'a normalize edilir

### Prompt Memory

**Dosya:** `lambda/video_creator/prompt_memory.py`
**Zamanlama:** Her Pazar 21:00 UTC

En iyi ve en kötü performans gösteren videoların hook'larından **DO** ve **DON'T** örnekleri çıkarır:

1. Tamamlanmış videoları retention'a göre sıralar
2. **Top 5** → DO örnekleri (başarılı hook'lar + neden iyi çalıştı)
3. **Bottom 5** → DON'T örnekleri (kötü hook'lar + neden başarısız)
4. Bu örnekler writer/evaluator prompt'larına enjekte edilir
5. Max 150 karakter per örnek

### Weekly Report

**Dosya:** `lambda/video_creator/weekly_report.py`
**Zamanlama:** Her Pazar 20:00 UTC

Haftalık performans özeti hazırlar ve SNS ile bildirim gönderir:
- Toplam eligible & complete video sayısı
- Ortalama predicted vs actual retention
- En iyi ve en kötü performans gösteren videolar
- Haftalık trend analizi

---

## 📊 YouTube Analytics Entegrasyonu

### Dosya: `lambda/video_creator/youtube_analytics.py`

### Akış

```
1. Video üretilir → DynamoDB'ye "pending" olarak kaydedilir
2. Kullanıcı YouTube'a yükler ve yayınlar
3. Admin panelinden "Link Video" ile YouTube URL'si girilir
4. Status "linked" olur
5. Analytics Fetcher (23:00 UTC) çalışır:
   - 24 saatten genç → atla (analytics hazır değil)
   - 24-72 saat → çekmeyi dene
   - 72+ saat veri yok → "failed" işaretle
6. Gerçek retention çekilir, tahminle karşılaştırılır
7. Status "complete" olur
8. Decision Engine (23:30 UTC) yeni verileri kullanır
```

### DynamoDB'de Saklanan Bilgiler (shorts_video_metrics)

| Alan                  | Açıklama                          |
|-----------------------|-----------------------------------|
| video_id              | Benzersiz ID (pending_YYYY-MM-DD_HH-MM-SS) |
| youtube_video_id      | YouTube video ID'si               |
| predicted_retention   | AI'ın tahmini (%)                 |
| actual_retention      | Gerçek YouTube değeri (%)         |
| hook_score            | Hook puanı (0-10)                 |
| status                | pending/linked/complete/failed    |
| calibration_eligible  | Kalibrasyon için uygun mu?        |

### Retry Stratejisi

```
Video yaşı < 24 saat  → Atla (veri hazır değil)
Video yaşı 24-72 saat → Dene, başarısız → sonraki gün tekrar dene
Video yaşı > 72 saat  → Veri yoksa "failed" işaretle
```

---

## 📋 İş Takibi (Job Tracking)

### DynamoDB Tabloları

Sistem üç ek DynamoDB tablosu kullanarak detaylı iş takibi ve loglama yapar:

#### `shorts_jobs` - İş Takibi
On-demand video üretim isteklerini takip eder.

| Alan             | Açıklama                          |
|------------------|-----------------------------------|
| job_id           | Benzersiz iş ID'si               |
| status           | queued → running → completed/failed |
| requested_at_utc | İstek zamanı                     |
| topic            | Video konusu                      |
| mode             | QUALITY / FAST                   |

- GSI: `by_date` (tarihe göre sıralama)
- TTL: 30 gün sonra otomatik temizleme

#### `shorts_run_logs` - Yapısal Loglar
Her video üretim sürecinin detaylı adım adım logları.

| Alan      | Açıklama                          |
|-----------|-----------------------------------|
| pk        | job_id                           |
| sk        | timestamp#component#seq          |
| component | video_generator / analytics_fetcher / decision_engine |
| level     | INFO / WARN / ERROR              |
| event     | Olay tipi (ör: script_generated) |
| message   | İnsan okunabilir mesaj           |
| payload   | Yapısal veri (JSON)              |

- GSI: `by_component_day` (günlük komponent sorguları)
- TTL: 14 gün sonra otomatik temizleme

#### `shorts_rate_limits` - API Rate Limiting
API isteklerini dakika bazında sayar.

- TTL: 2 dakika sonra otomatik temizleme
- Limit: Dakikada 2 generate isteği per API key

---

## 🖥️ Admin Paneli

### Dosyalar:
- `admin-panel/index.html` - Ana sayfa
- `admin-panel/app.js` - JavaScript logic
- `admin-panel/styles.css` - Stiller

### Hosting
Admin paneli **CloudFront + S3** ile statik olarak host edilir:
- S3 bucket'a HTML/JS/CSS dosyaları otomatik yüklenir (Terraform ile)
- CloudFront CDN üzerinden HTTPS ile erişilir
- SPA routing desteği (403/404 → index.html)

### API Endpoints (Admin Lambda)

| Method | Endpoint         | Açıklama                             |
|--------|------------------|--------------------------------------|
| GET    | /stats           | Dashboard istatistikleri             |
| GET    | /videos          | Video listesi (filtreli)             |
| GET    | /videos/{id}     | Tek video detayı                     |
| PATCH  | /videos/{id}     | Video güncelle (audit log ile)       |
| DELETE | /videos/{id}     | Video sil                            |
| POST   | /videos/bulk     | Toplu güncelleme (max 50)            |
| POST   | /generate        | On-demand video üretimi tetikle      |
| GET    | /jobs            | Son üretim işlerini listele          |
| GET    | /jobs/{id}       | İş detayı                            |
| GET    | /logs            | Yapısal çalışma logları              |

### Özellikler

- **Filtreleme**: Status, eligible, mode, pipeline
- **Link Video**: YouTube URL'si ekle (otomatik ID parse)
- **Mark as TEST**: Kalibrasyondan çıkar
- **Delete**: Test videolarını sil
- **Bulk Actions**: Çoklu seçim ve güncelleme
- **On-Demand Generate**: Belirli konu ve mod ile video üret
- **Rate Limiting**: Dakikada 2 istek limiti
- **Idempotency**: `client_request_id` ile duplicate engelleme
- **Job Monitoring**: Real-time iş durumu ve yapısal loglar

---

## ☁️ AWS Altyapısı

### Terraform Dosyaları

| Dosya                  | İçerik                                        |
|-----------------------|-----------------------------------------------|
| main.tf               | Provider, S3 video bucket, SNS                |
| lambda.tf             | Video Generator Lambda                         |
| analytics_lambda.tf   | Analytics Fetcher Lambda                       |
| autopilot_lambda.tf   | Decision Engine + Prompt Memory Lambda'ları    |
| api_admin.tf          | API Gateway + Admin Lambda                     |
| api_generate.tf       | /generate, /jobs, /logs API endpoints          |
| dynamodb_metrics.tf   | Video metrics tablosu                          |
| dynamodb_jobs.tf      | Jobs, run_logs, rate_limits tabloları          |
| s3_admin_panel.tf     | Admin panel S3 + CloudFront hosting            |
| iam.tf                | IAM rolleri ve politikaları                    |
| secrets.tf            | Secrets Manager referansları                   |
| variables.tf          | Terraform değişken tanımları                   |
| outputs.tf            | Terraform çıktıları (URL'ler, ARN'ler)        |

### AWS Servisleri

| Servis              | Kullanım                                |
|---------------------|------------------------------------------|
| Lambda              | Video üretimi, analytics, admin API, decision engine, prompt memory, weekly report |
| S3                  | Video, müzik, görseller, admin panel     |
| DynamoDB            | Video metrikleri, jobs, run logs, rate limits |
| API Gateway         | Admin panel REST API + Generate API      |
| EventBridge         | Zamanlanmış tetikleyiciler               |
| Bedrock (Claude)    | Senaryo yazımı ve puanlama               |
| Bedrock (Titan)     | AI görsel üretimi                        |
| Polly               | Text-to-Speech                           |
| SNS                 | Bildirimler                              |
| CloudFront          | Admin panel CDN (HTTPS)                  |
| Secrets Manager     | YouTube OAuth credentials                |
| CloudWatch          | Loglar                                   |

### EventBridge Zamanlamaları

| Lambda           | Zamanlama                   | Açıklama                        |
|------------------|-----------------------------|---------------------------------|
| Video Generator  | Her 8 saatte bir            | Otomatik video üretimi          |
| Analytics Fetcher| Her gün 23:00 UTC           | YouTube verilerini çek          |
| Decision Engine  | Her gün 23:30 UTC           | Autopilot ağırlıkları güncelle  |
| Weekly Report    | Pazar 20:00 UTC             | Haftalık performans raporu      |
| Prompt Memory    | Pazar 21:00 UTC             | DO/DON'T örneklerini güncelle   |

---

## 🚀 Kurulum

### Öngereksinimler

1. **AWS CLI** yapılandırılmış
2. **Terraform** kurulu
3. **Python 3.11+** kurulu
4. **AWS Bedrock'ta Claude 3 ve Titan modelleri etkinleştirilmiş**

### Adımlar

```powershell
# 1. Repo'yu klonla
git clone https://github.com/your-repo/historical-shorts.git
cd historical-shorts

# 2. Setup script'i çalıştır (FFmpeg + Python layer'ları hazırlar)
.\setup.ps1    # Windows
# veya
./setup.sh     # Linux/Mac

# 3. Terraform değişkenlerini ayarla
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars dosyasını düzenle

# 4. Terraform ile deploy et
terraform init
terraform apply

# 5. YouTube OAuth token al (bir kerelik)
cd ..
python get_youtube_token.py

# 6. Admin paneli (CloudFront URL terraform output'ta)
# veya local test için:
cd admin-panel
python -m http.server 8080
# Tarayıcıda http://localhost:8080 aç
```

### Lambda Layer'ları

Sistem iki Lambda layer'ı kullanır (setup script'i bunları hazırlar):

| Layer          | İçerik                    | Dosya                         |
|----------------|---------------------------|-------------------------------|
| FFmpeg Layer   | FFmpeg binary (video işleme) | `lambda/layer/ffmpeg-layer.zip` |
| Python Deps    | requests vb. bağımlılıklar  | `lambda/layer/python-deps.zip`  |

### Müzik Dosyaları

S3'e royalty-free müzik yükle:
```
s3://bucket-name/music/loops/cinematic_1.mp3
s3://bucket-name/music/loops/epic_1.mp3
s3://bucket-name/music/loops/emotional_1.mp3
...
```

---

## 📂 Dosya Yapısı

```
historical/
├── README.md                    # Bu dosya
├── setup.ps1                    # Windows setup script
├── setup.sh                     # Linux/Mac setup script
├── download_ffmpeg.py           # FFmpeg indirme yardımcısı
├── download_font.py             # Font indirme yardımcısı
├── get_youtube_token.py         # YouTube OAuth token alma
├── payload.json                 # Lambda test payload'u
│
├── admin-panel/                 # Web admin paneli
│   ├── index.html               # Ana sayfa
│   ├── app.js                   # JavaScript logic (29KB)
│   └── styles.css               # Stiller (35KB)
│
├── lambda/                      # Lambda fonksiyonları
│   ├── layer/                   # Lambda layer'ları
│   │   ├── ffmpeg-layer.zip     # FFmpeg binary
│   │   ├── python-deps.zip      # Python bağımlılıkları
│   │   └── README.md            # Layer dokümantasyonu
│   │
│   ├── admin_api/
│   │   └── handler.py           # Admin API handler (CRUD + generate + jobs + logs)
│   │
│   └── video_creator/           # Ana video üretim modülü
│       ├── handler.py              # Ana Lambda handler (orchestrator + job tracking)
│       ├── script_pipeline.py      # Senaryo + puanlama sistemi (iteratif)
│       ├── script_gen.py           # Senaryo generator
│       ├── topic_selector.py       # 🆕 History Buffet konu seçim stratejisi
│       ├── stock_fetcher.py        # 🆕 Visual Director — 4 katmanlı sinematik prompt
│       ├── titan_sanitizer.py      # Prompt güvenlik filtresi + yüz kaçınma
│       ├── video_composer.py       # FFmpeg video birleştirme
│       ├── tts.py                  # AWS Polly ses üretimi
│       ├── subtitle_gen.py         # Altyazı oluşturma
│       ├── music_fetcher.py        # S3'den müzik çekme
│       ├── smart_music_cutter.py   # Akıllı müzik kesimi
│       ├── story_music_matcher.py  # Mood-müzik eşleştirme
│       ├── sfx_generator.py        # Ses efektleri
│       ├── decision_engine.py      # Thompson Sampling autopilot + kategori feedback
│       ├── prompt_memory.py        # Haftalık DO/DON'T güncelleme
│       ├── weekly_report.py        # Haftalık performans raporu
│       ├── youtube_analytics.py    # YouTube API entegrasyonu
│       ├── metrics_correlator.py   # Tahmin-gerçek karşılaştırma
│       ├── similarity_dampener.py  # Konu çeşitliliği kontrolü
│       ├── copyright_safety.py     # Telif hakkı takibi
│       ├── utils/
│       │   └── analytics_score.py  # 🆕 Virality Score hesaplama
│       ├── requirements.txt        # Python bağımlılıkları
│       └── font.ttf                # Altyazı fontu
│
├── terraform/                   # AWS altyapı tanımları
│   ├── main.tf                  # Provider, S3, SNS
│   ├── lambda.tf                # Video Generator Lambda
│   ├── analytics_lambda.tf      # Analytics Fetcher Lambda
│   ├── autopilot_lambda.tf      # Decision Engine + Prompt Memory
│   ├── api_admin.tf             # API Gateway + Admin Lambda
│   ├── api_generate.tf          # Generate/Jobs/Logs API endpoints
│   ├── dynamodb_metrics.tf      # Video metrics tablosu
│   ├── dynamodb_jobs.tf         # Jobs + Run Logs + Rate Limits tabloları
│   ├── s3_admin_panel.tf        # CloudFront + S3 admin panel hosting
│   ├── iam.tf                   # IAM rolleri ve politikaları
│   ├── secrets.tf               # Secrets Manager referansları
│   ├── variables.tf             # Terraform değişkenleri
│   ├── outputs.tf               # Terraform çıktıları
│   ├── terraform.tfvars.example # Örnek değişken dosyası
│   └── autopilot_seed.json      # Autopilot başlangıç konfigürasyonu
│
└── tests/                       # Test dosyaları
    ├── test_virality_score.py      # 🆕 Virality Score testleri
    ├── test_topic_selector.py      # 🆕 Konu seçim testleri
    ├── test_visual_director.py     # 🆕 Visual Director testleri
    └── test_query_logic.py         # Query logic testleri
```

---

## 🔧 Konfigürasyon

### Ortam Değişkenleri (Lambda)

| Değişken            | Açıklama                        |
|---------------------|---------------------------------|
| AWS_REGION_NAME     | AWS bölgesi (us-east-1)         |
| METRICS_TABLE_NAME  | DynamoDB video metrics tablosu  |
| JOBS_TABLE_NAME     | DynamoDB jobs tablosu           |
| RUN_LOGS_TABLE_NAME | DynamoDB run logs tablosu       |
| RATE_LIMITS_TABLE_NAME | DynamoDB rate limits tablosu |
| VIDEO_BUCKET        | S3 video bucket adı             |
| YOUTUBE_SECRET_ARN  | YouTube OAuth secret ARN        |
| SNS_TOPIC_ARN       | Bildirim SNS topic ARN          |

### Puanlama Ayarları

`script_pipeline.py` içinde değiştirilebilir:

```python
HOOK_THRESHOLD = 9.0          # Hook minimum puanı
SECTION_THRESHOLD = 8.5       # Diğer bölümler minimum
HOOK_MAX_ITERATIONS = 5       # Hook max deneme
SECTION_MAX_ITERATIONS = 3    # Diğer bölümler max deneme
```

### Autopilot Ayarları

`decision_engine.py` içinde güvenlik sınırları:

```python
WEIGHT_BOUNDS = {
    "mode": {"QUALITY": (0.3, 0.9), "FAST": (0.1, 0.5)},
    "title": {"bold": (0.2, 0.8), "safe": (0.1, 0.6), "experimental": (0.05, 0.4)},
    ...
}

DECAY_WEIGHTS = {
    7: 1.0,    # 0-7 gün: tam ağırlık
    14: 0.5,   # 8-14 gün: yarım ağırlık
    21: 0.25,  # 15-21 gün: çeyrek ağırlık
    999: 0.1   # 22+ gün: minimal ağırlık
}
```

---

## 📈 Maliyet Tahmini

| Servis         | Günlük ~3 video için |
|----------------|----------------------|
| Lambda         | ~$0.50               |
| Bedrock Claude | ~$1.50               |
| Bedrock Titan  | ~$0.40               |
| Polly          | ~$0.10               |
| S3             | ~$0.02               |
| DynamoDB       | ~$0.02               |
| CloudFront     | ~$0.01               |
| **Toplam**     | **~$2.55/gün**       |

---

## 🐛 Sorun Giderme

### Video çok kısa çıkıyor
- Klip sürelerini kontrol et (`stock_fetcher.py` - 8 saniye olmalı)
- Voiceover süresini kontrol et

### Titan görsel üretmiyor
- `titan_sanitizer.py` loglarını kontrol et
- Prompt'ta yasaklı kelime olabilir

### CORS hatası
- API Gateway'i redeploy et: `aws apigateway create-deployment --rest-api-id XXX --stage-name v1`

### Analytics çekilmiyor
- YouTube OAuth token'ı kontrol et
- Video en az 24 saat önce yayınlanmış olmalı

### Decision Engine çalışmıyor
- `shorts_video_metrics` tablosunda `status=complete` ve `calibration_eligible=true` olan video olmalı
- CloudWatch loglarını kontrol et: `youtube-shorts-decision-engine`

### Admin paneli 403/404 hatası
- CloudFront invalidation çalıştır: `aws cloudfront create-invalidation --distribution-id XXX --paths "/*"`
- S3 bucket policy'yi kontrol et

### Job durumu "queued" kalmış
- Lambda timeout'unu kontrol et (default: 300s)
- CloudWatch loglarından hatayı bul
- `shorts_run_logs` tablosundan yapısal log'ları incele

---

## 📞 Destek

Sorular için issue açabilirsiniz.

---

*Son güncelleme: 2026-02-12*
