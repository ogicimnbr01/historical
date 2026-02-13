# 🎬 YouTube Shorts AI Video Generator

**Tam otomatik, kendi kendini öğreten YouTube Shorts video üretim sistemi**

Tarihsel içerikler için AI destekli video üretimi yapar. Senaryo yazımından video render'ına, kalite skorlamasından YouTube Analytics takibine kadar tüm süreç otomatiktir. **Thompson Sampling** tabanlı autopilot sistemi ile parametreler gerçek YouTube performansına göre sürekli optimize edilir.

### 🆕 Son Güncellemeler (v2.4 — Scientific Phase)
- **🔬 Kalibrasyon Raporu**: 8 analiz ile evaluator doğruluğunu test eden bilimsel rapor sistemi
- **📏 Refine Delta Enstrümantasyonu**: `first_hook_score → final_hook_score` delta ile self-optimization tespiti
- **📊 Pearson Korelasyon Testi**: Hook score delta ↔ actual retention korelasyonu (Goodhart guardrail)
- **⚖️ Dual Jury Evaluator**: Sonnet (yapı) + Haiku (dikkat) ikili jüri — weighted scoring (S×0.4 + H×0.6)
- **🎯 Targeted Refine**: Haiku diagnostik verisi refiner'a enjekte ediliyor — cerrahi müdahale
- **🏄 Retention-Aware Diversity**: Yüksek retention (≥55%) alan kategoriler tekrar edebilir (wave surfing)
- **📊 Virality Score**: Retention × 1.5 + Stopping Power × 2.0
- **🎬 Visual Director**: 4 katmanlı sinematik prompt sistemi
- **🌍 Antropoloji & Kültür**: Yeni kategori — Aztek Ölüm Düdüğü, Tibet Gökyüzü Cenazesi

---

## 📋 İçindekiler

1. [Sistem Mimarisi](#-sistem-mimarisi)
2. [Video Üretim Pipeline](#-video-üretim-pipeline)
3. [Senaryo Pipeline (Dual Jury)](#-senaryo-pipeline-dual-jury)
4. [Kalibrasyon ve Bilimsel Faz](#-kalibrasyon-ve-bilimsel-faz)
5. [Konu Seçim Stratejisi (History Buffet)](#-konu-seçim-stratejisi-history-buffet)
6. [Virality Score](#-virality-score-performans-puanlama)
7. [Görsel Üretimi (Visual Director)](#-görsel-üretimi-visual-director)
8. [Ses & Müzik](#-ses--müzik)
9. [Autopilot Sistemi](#-autopilot-sistemi)
10. [YouTube Analytics](#-youtube-analytics-entegrasyonu)
11. [Admin Paneli & API](#-admin-paneli--api)
12. [AWS Altyapısı & Deployment](#-aws-altyapısı--deployment)
13. [Konfigürasyon](#-konfigürasyon)
14. [Sorun Giderme](#-sorun-giderme)

---

## 🌟 Sistem Mimarisi

### Yüksek Seviye Mimari

```mermaid
graph TB
    subgraph Triggers["⏰ Tetikleyiciler"]
        EB1["EventBridge<br/>Her 8 saat"]
        EB2["EventBridge<br/>23:00 UTC"]
        EB3["EventBridge<br/>23:30 UTC"]
        EB4["EventBridge<br/>Pazar 20-21 UTC"]
        API["API Gateway<br/>POST /generate"]
    end

    subgraph Core["🎬 Video Üretim"]
        VG["Video Generator<br/>Lambda"]
        SP["Script Pipeline<br/>Dual Jury + Refine"]
        VD["Visual Director<br/>Titan Image"]
        TTS["AWS Polly<br/>TTS"]
        FC["FFmpeg<br/>Compositor"]
    end

    subgraph Intelligence["🧠 Zeka Katmanı"]
        AF["Analytics Fetcher<br/>YouTube API"]
        DE["Decision Engine<br/>Thompson Sampling"]
        PM["Prompt Memory<br/>DO/DON'T"]
        WR["Weekly Report"]
        CR["Calibration Report<br/>8 Analiz"]
    end

    subgraph Storage["💾 Veri Katmanı"]
        S3["S3<br/>Video + Müzik + Görseller"]
        DDB["DynamoDB<br/>Metrikler + Jobs + Logs"]
        SM["Secrets Manager<br/>YouTube OAuth"]
    end

    subgraph AI["🤖 AI Servisleri"]
        Sonnet["Claude Sonnet<br/>Writer + Yapı Jürisi"]
        Haiku["Claude Haiku<br/>Dikkat Jürisi"]
        Titan["Titan<br/>Image Generator"]
    end

    EB1 --> VG
    API --> VG
    EB2 --> AF
    EB3 --> DE
    EB4 --> PM
    EB4 --> WR

    VG --> SP
    SP --> Sonnet
    SP --> Haiku
    VG --> VD
    VD --> Titan
    VG --> TTS
    VG --> FC

    VG --> S3
    VG --> DDB
    AF --> SM
    AF --> DDB
    DE --> DDB
    CR --> DDB

    style SP fill:#ff6b6b,stroke:#333,color:#fff
    style CR fill:#ffd93d,stroke:#333,color:#333
    style DE fill:#6bcb77,stroke:#333,color:#fff
```

### Kapalı Döngü Optimizasyon

```mermaid
graph LR
    A["🎬 Video Üret"] --> B["📤 YouTube'a Yükle"]
    B --> C["📊 Analytics Çek<br/>(24-72 saat sonra)"]
    C --> D["🧮 Virality Score<br/>Hesapla"]
    D --> E["🎰 Thompson Sampling<br/>Ağırlık Güncelle"]
    E --> F["📝 Prompt Memory<br/>DO/DON'T"]
    F --> A

    C --> G["🔬 Kalibrasyon<br/>Raporu"]
    G --> H{"Self-Optimization<br/>Tespiti?"}
    H -->|Evet| I["⚠️ Refine Kısıtla"]
    H -->|Hayır| J["✅ Devam"]

    style G fill:#ffd93d,stroke:#333,color:#333
    style H fill:#ff6b6b,stroke:#333,color:#fff
```

---

## 🔄 Video Üretim Pipeline

### Adım Adım Akış

```mermaid
flowchart TD
    START([🚀 Başla]) --> CONFIG["Autopilot Config Yükle<br/>Mode + Hook Family + Title"]
    CONFIG --> TOPIC["Konu Seç<br/>History Buffet + Diversity"]
    TOPIC --> SCRIPT["Senaryo Pipeline<br/>Dual Jury + Refine"]

    SCRIPT --> HOOK["Hook Üret<br/>3 varyant → Dual Jury"]
    HOOK --> HOOKQ{Score ≥ 9.0?}
    HOOKQ -->|Hayır| REFHOOK["Targeted Refine<br/>(max 2 refine)"]
    REFHOOK --> HOOKQ
    HOOKQ -->|Evet| CTX["Context Üret<br/>2 varyant → Dual Jury"]

    CTX --> BODY["Body Üret"] --> OUTRO["Outro Üret"]

    OUTRO --> KPI["KPI Tahmin Et<br/>Clarity + Curiosity + Swipe Risk"]
    KPI --> VISUAL["4× Görsel Üret<br/>Visual Director + Titan"]
    VISUAL --> VOICE["Seslendirme<br/>AWS Polly"]
    VOICE --> MUSIC["Müzik Seç + Kes"]
    MUSIC --> FFMPEG["FFmpeg Render<br/>1080×1920 9:16"]
    FFMPEG --> UPLOAD["S3 Yükle + DynamoDB Kaydet"]
    UPLOAD --> SNS["📱 SNS Bildirim"]
    SNS --> DONE([✅ Bitti])

    style HOOK fill:#ff6b6b,stroke:#333,color:#fff
    style KPI fill:#ffd93d,stroke:#333,color:#333
    style FFMPEG fill:#4ecdc4,stroke:#333,color:#fff
```

---

## 📝 Senaryo Pipeline (Dual Jury)

### Dosya: `lambda/video_creator/script_pipeline.py`

Bu dosya sistemin **kalbi**. Her senaryo parçası ikili jüri sistemiyle puanlanır ve iteratif olarak iyileştirilir.

### Pipeline Modları

```mermaid
graph LR
    subgraph FAST["⚡ FAST Mode"]
        F1["Hook Threshold: 8.7"]
        F2["Section Threshold: 8.3"]
        F3["Hook Max: 3 iter (2 refine)"]
        F4["Section Max: 2 iter (1 refine)"]
        F5["Max API: 12 çağrı"]
    end

    subgraph QUALITY["💎 QUALITY Mode"]
        Q1["Hook Threshold: 9.0"]
        Q2["Section Threshold: 8.5"]
        Q3["Hook Max: 3 iter (2 refine)"]
        Q4["Section Max: 2 iter (1 refine)"]
        Q5["Max API: 30 çağrı"]
    end

    style FAST fill:#4ecdc4,stroke:#333,color:#fff
    style QUALITY fill:#ff6b6b,stroke:#333,color:#fff
```

### Dual Jury Sistemi

```mermaid
graph TD
    WRITER["✍️ Writer (Sonnet)<br/>Hook / Section üretir"] --> EVAL

    subgraph EVAL["⚖️ Dual Jury Değerlendirme"]
        direction LR
        SONNET["🏛️ Sonnet Jürisi<br/>Yapı Koruyucu<br/>Ağırlık: 40%"]
        HAIKU["👁️ Haiku Jürisi<br/>Dikkat Simülatörü<br/>Ağırlık: 60%"]
    end

    EVAL --> CALC["Weighted Score<br/>S×0.4 + H×0.6"]
    CALC --> FLOOR{"Sonnet ≥ 6.5?"}
    FLOOR -->|Hayır| REJECT["❌ Reject<br/>(Kalite Guardrail)"]
    FLOOR -->|Evet| CHECK{"Score ≥ Threshold?"}
    CHECK -->|Evet| APPROVE["✅ Onay"]
    CHECK -->|Hayır| DIAG["Haiku Diagnostik"]

    DIAG --> REFINE["🔧 Targeted Refine"]
    REFINE --> |"skip_reason<br/>drop_word<br/>fixes"| WRITER

    style HAIKU fill:#ff6b6b,stroke:#333,color:#fff
    style SONNET fill:#4ecdc4,stroke:#333,color:#fff
    style REJECT fill:#333,stroke:#ff0000,color:#fff
```

### Hook vs Section Karşılaştırması

| Özellik | Hook 🎯 | Section 📄 |
|---------|---------|-----------|
| İlk üretim | **3** varyant (batch) | **2** varyant |
| Threshold (Quality) | **9.0** | **8.5** |
| Max iterasyon | **3** (2 refine) | **2** (1 refine) |
| Tie-breaker | Clarity → Kısa kazanır | Outro: punch / Context: kısa |
| Etki alanı | İlk 1-3 saniye (binary) | Orta retention (kademeli) |
| **Self-optimization riski** | **🔴 Yüksek** | 🟢 Düşük |

### Targeted Refine (Cerrahi İyileştirme)

```
❌ Eski (Kör Refine):
  "Fix these issues: too predictable"

✅ Yeni (Cerrahi Refine):
  Viewer Attention Diagnostics:
  • Skip Reason: "Sounds like a History Channel intro"
  • Drop Word: "army" ← dikkat burada düşüyor
  • Attention Failure: Predictable phrasing
  Rewrite Constraints:
  • Replace predictable military framing
  • Introduce escalation or absurdity
  • Maintain factual accuracy
```

### KPI Proxy Metrics

| Metrik | Açıklama | Aralık |
|--------|----------|--------|
| `instant_clarity` | İlk saniyede ne olduğu anlaşılıyor mu? | 0-10 |
| `curiosity_gap` | "Sonra ne oldu?" merakı uyandırıyor mu? | 0-10 |
| `swipe_risk` | Kaydırma riski (yüksek = düşük risk) | 0-10 |
| `predicted_retention` | Tahmini izlenme yüzdesi | 0-100 |

---

## 🔬 Kalibrasyon ve Bilimsel Faz

### Dosya: `lambda/video_creator/calibration_report.py`

Sistem artık **spekülasyon değil, deney** yapıyor. Kalibrasyon raporu 8 farklı analizle evaluator'ın gerçekliğini test eder.

### Anti-Goodhart Mimari

```mermaid
graph TD
    subgraph RISK["⚠️ Goodhart Riski"]
        R1["Evaluator rubric ile skorluyor"]
        R2["Diagnostik feedback üretiyor"]
        R3["Writer feedback'e göre rewrite yapıyor"]
        R4["Aynı evaluator tekrar skorluyor"]
        R1 --> R2 --> R3 --> R4
        R4 -->|"Self-optimization<br/>loop"| R1
    end

    subgraph GUARD["🛡️ Anti-Goodhart Guardrails"]
        G1["first_hook_score<br/>Pre-refine skoru kaydet"]
        G2["final_hook_score<br/>Post-refine skoru kaydet"]
        G3["Pearson Correlation<br/>delta ↔ retention"]
        G4["Refine Bucket Eğrisi<br/>0/1/2/3/4+"]
    end

    R4 --> G1
    G1 --> G3
    G2 --> G3
    G3 --> DECISION{"corr > 0.3?"}
    DECISION -->|Evet| OK["✅ Gerçek Sinyal"]
    DECISION -->|"corr < 0.1<br/>AND delta > 0.5"| BAD["❌ Self-Optimization"]
    DECISION -->|Gri bölge| WAIT["⚠️ Daha Fazla Veri"]

    style RISK fill:#ff6b6b,stroke:#333,color:#fff
    style GUARD fill:#6bcb77,stroke:#333,color:#fff
    style BAD fill:#333,stroke:#ff0000,color:#fff
```

### 8 Analiz Modülü

```mermaid
graph LR
    subgraph REPORT["📊 Kalibrasyon Raporu"]
        A1["1. Spearman Korelasyonlar<br/>hook_score ↔ retention"]
        A2["2. Kalibrasyon Eğrisi<br/>predicted vs actual"]
        A3["3. Refine Impact<br/>0/1/2/3/4+ bucket"]
        A4["4. Hook Score Bantları<br/>9.0+ vs 8.5-8.9"]
        A5["5. Explore vs Exploit<br/>Bandit dengesi"]
        A6["6. Outlier Analizi<br/>Tehlikeli sapmalar"]
        A7["7. Kategori Heatmap<br/>Performans dağılımı"]
        A8["8. Refine Delta 🆕<br/>Self-optimization testi"]
    end

    style A8 fill:#ffd93d,stroke:#333,color:#333
    style A1 fill:#4ecdc4,stroke:#333,color:#fff
```

| # | Analiz | Ne Sorar? | Kritik Metrik |
|---|--------|-----------|---------------|
| 1 | **Spearman Korelasyonlar** | Skorlar retention'ı tahmin ediyor mu? | ρ değeri |
| 2 | **Kalibrasyon Eğrisi** | Yüksek tahmin = yüksek gerçek mi? | Bias (pp) |
| 3 | **Refine Impact** | Daha fazla refine = daha iyi mi? | Bucket eğrisi |
| 4 | **Hook Score Bantları** | 9.0 eşiği haklı mı? | Band retention farkı |
| 5 | **Explore vs Exploit** | Bandit yeterince keşfediyor mu? | Explore oranı |
| 6 | **Outlier Analizi** | Model nerede tehlikeli yanılıyor? | Max hata |
| 7 | **Kategori Heatmap** | Hangi kategori gerçekten kazanıyor? | Avg retention by category |
| 8 | **🆕 Refine Delta** | Evaluator kendini mi ödüllendiriyor? | Pearson(delta, retention) |

### Refine Delta Enstrümantasyonu

```mermaid
sequenceDiagram
    participant W as Writer (Sonnet)
    participant E as Evaluator (Dual Jury)
    participant DB as DynamoDB
    participant YT as YouTube

    Note over W,E: Iteration 0 — İlk Üretim
    W->>E: 3 hook üret
    E->>E: Dual Jury skorla
    E->>DB: first_hook_score = 8.2 📏

    Note over W,E: Iteration 1 — Refine
    E->>W: skip_reason + drop_word
    W->>E: Refined hook
    E->>E: Dual Jury tekrar skorla
    E->>DB: final_hook_score = 9.1 📏

    Note over DB: hook_score_delta = +0.9

    Note over YT: 48 saat sonra...
    YT->>DB: actual_retention = 47%

    Note over DB: Pearson(all deltas, all retentions)<br/>corr < 0.1 → ❌ Self-optimization
```

### Karar Matrisi

| Senaryo | hook_score_delta | retention_delta | Pearson corr | Aksiyon |
|---------|-----------------|-----------------|-------------|---------|
| **A — İdeal** | +0.3–0.8 | Pozitif | > 0.3 | ✅ Devam |
| **B — Selection Kazancı** | ≈ 0.0 | Pozitif | N/A | Refine gereksiz |
| **C — Goodhart** | ≥ 1.0 | Sıfır/Negatif | < 0.1 | ❌ Refine kesilir |

### Refine Bucket Eğrisi — Beklenen Senaryolar

```mermaid
graph LR
    subgraph HEALTHY["✅ Sağlıklı (Ters U)"]
        H0["0 refine<br/>45%"] --> H1["1 refine<br/>52%"]
        H1 --> H2["2 refine<br/>48%"]
    end

    subgraph STERILE["❌ Sterilizasyon"]
        S0["0 refine<br/>48%"] --> S1["1 refine<br/>46%"]
        S1 --> S2["2 refine<br/>41%"]
    end

    subgraph SIGNAL["💎 Gerçek Sinyal"]
        G0["0 refine<br/>42%"] --> G1["1 refine<br/>50%"]
        G1 --> G2["2 refine<br/>53%"]
    end

    style HEALTHY fill:#ffd93d,stroke:#333,color:#333
    style STERILE fill:#ff6b6b,stroke:#333,color:#fff
    style SIGNAL fill:#6bcb77,stroke:#333,color:#fff
```

### DynamoDB'de Saklanan Kalibrasyon Verileri

| Alan | Kaynak | Açıklama |
|------|--------|----------|
| `hook_score` | pipeline | Final weighted hook score |
| `predicted_retention` | KPI evaluator | Tahmini retention (%) |
| `actual_retention` | YouTube Analytics | Gerçek retention (%) |
| `refine_total` | pipeline stats | Toplam refine sayısı |
| `hook_refines` | pipeline stats | Sadece hook refine sayısı |
| `first_hook_score` 🆕 | pipeline stats | İlk iterasyon hook skoru |
| `final_hook_score` 🆕 | pipeline stats | Son iterasyon hook skoru |
| `category` | topic selector | Video kategorisi |
| `pipeline_mode` | config | QUALITY / FAST |
| `hook_family` | config | contradiction / shock / mystery... |

---

## 🎯 Konu Seçim Stratejisi (History Buffet)

### Dosya: `lambda/video_creator/topic_selector.py`

```mermaid
graph TD
    START["Konu Seçimi Başla"] --> WEIGHTS["Kategori Ağırlıkları Yükle<br/>(Autopilot tarafından güncellenir)"]
    WEIGHTS --> LAST["Son Videonun Kategorisini Çek"]
    LAST --> RETENTION{"Son 5 videonun<br/>avg retention?"}

    RETENTION -->|"≥ 55%"| WAVE["🏄 Wave Surfing!<br/>Aynı kategori tekrar seçilebilir"]
    RETENTION -->|"< 55%"| BLOCK["🔄 Blokla<br/>Farklı kategori seç"]

    WAVE --> SELECT["Ağırlıklı Rastgele Seçim"]
    BLOCK --> SELECT
    SELECT --> SIM{"Similarity<br/>Dampener"}
    SIM -->|"Çok benzer"| SELECT
    SIM -->|"Farklı"| TOPIC["✅ Konu Seçildi"]
```

### Kategori Dağılımı

| Kategori | Ağırlık | Örnek Konular |
|----------|---------|---------------|
| 🔫 Modern Savaş | **30%** | Ghost Army, White Death, Manhattan Project |
| 🏛️ Antik Çağ | **25%** | Spartalılar, Sezar'ın intikamı, Mansa Musa |
| ⚔️ Ortaçağ | **20%** | Samurai vs Şövalye, Paris kuşatması, Cengiz Han |
| 🔍 Gizem | **15%** | Korsan Kralı, Karıncalanma Vebası, Alcatraz |
| 👑 Liderler | **10%** | Napoleon, Fatih Sultan Mehmet, İskender |
| 🌍 Antropoloji | **10%** | Aztek Ölüm Düdüğü, Tibet Gökyüzü Cenazesi |

### Retention-Aware Diversity

YouTube algoritması momentum sever. Bir kategori yüksek retention alıyorsa, seed audience zaten o kategoriden besleniyordur:

```python
RETENTION_WAVE_THRESHOLD = 55.0  # % — bu üstünde tekrara izin ver

if cat_retention >= RETENTION_WAVE_THRESHOLD:
    # 🏄 Wave Surfing: Dalga iyiyse sörf devam
else:
    weights[last_category] = 0.0  # Normal diversity bloklaması
```

---

## 📊 Virality Score (Performans Puanlama)

### Dosya: `lambda/video_creator/utils/analytics_score.py`

```
Virality Score = (Retention × 1.5 + Stopping Power × 2.0) × log₁₀(Views)
```

| Bileşen | Açıklama | Ağırlık |
|---------|----------|---------|
| **Retention** | Ortalama izlenme yüzdesi (%) | ×1.5 |
| **Stopping Power** | `(1.0 - Swipe Rate) × 100` | ×2.0 |
| **Volume** | `log₁₀(Views)` — hacim çarpanı | ×1.0 |

> **Not:** Minimum 100 view gerekir. Altındaki videolar 0 puan alır.

### Neden Like'ları Yok Sayıyoruz?

```mermaid
graph LR
    LIKE["👍 Like"] -->|"Pasif sinyal"| IGNORE["Yok sayılır"]
    RET["📊 Retention"] -->|"İzleyici gerçekten izliyor mu?"| CORE["Ağırlık: 1.5×"]
    SP["🛑 Stopping Power"] -->|"Hook kaydırmayı durduruyor mu?"| CORE2["Ağırlık: 2.0×"]

    style IGNORE fill:#999,stroke:#333,color:#fff
    style CORE fill:#6bcb77,stroke:#333,color:#fff
    style CORE2 fill:#ff6b6b,stroke:#333,color:#fff
```

| Video Tipi | Retention | Swipe Rate | Views | Skor |
|------------|-----------|------------|-------|------|
| 🔥 Viral Hit | %80 | %30 | 10,000 | **~1,040** |
| 💎 Niche Gem | %95 | %10 | 1,000 | **~700** |
| 💀 Clickbait | %30 | %60 | 50,000 | **~587** |

---

## 🎬 Görsel Üretimi (Visual Director)

### Dosya: `lambda/video_creator/stock_fetcher.py`

### 4 Katmanlı Prompt Mimarisi

```mermaid
graph TD
    subgraph LAYERS["Visual Director — 4 Katman"]
        L1["🎨 1. GLOBAL STYLE<br/>cinematic historical illustration,<br/>dark fantasy graphic novel art style"]
        L2["🏛️ 2. ERA CONTEXT<br/>15th century Ottoman period,<br/>ornate armor, turbans, huge cannons"]
        L3["🎬 3. SCENE ACTION<br/>young Ottoman sultan commanding<br/>troops before fortress walls"]
        L4["🌙 4. MOOD<br/>dramatic lighting, volumetric fog,<br/>tense atmosphere, cinematic shot"]
    end

    L1 --> L2 --> L3 --> L4
    L4 --> TITAN["🖼️ Titan Image Generator"]
    TITAN --> KB["Ken Burns Effect<br/>Zoom / Pan / Fade"]

    style L1 fill:#ff6b6b,stroke:#333,color:#fff
    style L2 fill:#ffd93d,stroke:#333,color:#333
    style L3 fill:#4ecdc4,stroke:#333,color:#fff
    style L4 fill:#6c5ce7,stroke:#333,color:#fff
```

### Dönem Görsel DNA

| Dönem | Görsel DNA |
|-------|------------|
| Ottoman | Ornate armor, minarets, bombards |
| Roman | Legionary armor, marble columns |
| Viking | Longships, chainmail, foggy landscapes |
| Medieval | Knights, castles, heraldry banners |
| WW2 | 1940s gear, tanks, gritty war photography |
| Ancient | Stone temples, bronze weapons |
| Anthropology | Indigenous attire, ceremonial objects |

### Güvenlik: Titan Sanitizer

```python
# Prompt dönüşüm örnekleri
"war" → "soldiers in marching formation"
"Genghis Khan" → "13th century Mongol emperor in golden armor"
"blood" → "crimson sunset"

# Yüz kaçınma
"Mehmed II" → "young Ottoman ruler in golden armor"
"Napoleon" → "French military commander with bicorne hat"
```

---

## 🎙️ Ses & Müzik

### TTS (AWS Polly)

| Özellik | Değer |
|---------|-------|
| Ses tipi | Neural (doğal ses) |
| Sesler | Matthew, Brian, Stephen |
| Hız | 92-95% (biraz yavaş — dramatik) |
| Pitch | -5% ile -10% (derin ses) |

### Fonetik Yazım

```python
PHONETIC_REPLACEMENTS = {
    "Atatürk": "Ah-tah-turk",
    "Fatih": "Fah-teeh",
    "Constantinople": "Con-stan-tin-oh-pull",
    "Selahaddin": "Seh-lah-had-deen",
}
```

### Müzik Pipeline

```mermaid
graph LR
    MOOD["Story Music Matcher<br/>Mood analizi"] --> FETCH["Music Fetcher<br/>S3'den çek"]
    FETCH --> CUT["Smart Music Cutter<br/>En yüksek enerji segmenti"]
    CUT --> MIX["FFmpeg Mix<br/>Voice: 100% / Music: 55% / SFX: 40%"]

    style MIX fill:#6c5ce7,stroke:#333,color:#fff
```

| Kategori | Ne Zaman? |
|----------|-----------|
| epic | Savaş, fetih, imparatorluk |
| emotional | Kişisel hikayeler, trajedi |
| documentary | Genel tarihsel anlatım |
| dramatic | Gerilimli anlar |
| oriental | Osmanlı, Arap, Asya |

---

## 🤖 Autopilot Sistemi

### Thompson Sampling — Kapalı Döngü

```mermaid
graph TD
    subgraph ARMS["🎰 Bandit Arms"]
        MODE["Mode<br/>QUALITY / FAST"]
        TITLE["Title<br/>bold / safe / experimental"]
        HOOK["Hook Family<br/>contradiction / shock / mystery<br/>question / challenge / contrast"]
        CAT["Category<br/>6 kategori"]
    end

    subgraph CYCLE["🔄 Günlük Güncelleme (23:30 UTC)"]
        SCORE["Virality Score hesapla"]
        REWARD["Reward hesapla<br/>(winsorization + decay)"]
        BETA["Beta distribution güncelle"]
        SOFTMAX["Softmax → yeni ağırlıklar"]
        SAFETY["Safety bounds uygula<br/>(max %15 günlük değişim)"]
    end

    ARMS --> SCORE --> REWARD --> BETA --> SOFTMAX --> SAFETY --> ARMS

    style CYCLE fill:#e8f5e9,stroke:#333
```

### Decay Weights

| Video Yaşı | Ağırlık |
|------------|---------|
| 0-7 gün | 1.0 |
| 8-14 gün | 0.5 |
| 15-21 gün | 0.25 |
| 22+ gün | 0.1 |

### Guardrails

- **Recovery Mode:** Art arda 3 video retention < %25 → otomatik QUALITY mode
- Günlük max ağırlık değişimi: **%15**
- Kategori ağırlıkları her zaman toplam **1.0**'a normalize
- Safety bounds ile aşırı uçlara kayma engellenir

### Prompt Memory (Pazar 21:00 UTC)

```mermaid
graph LR
    VIDEOS["Tüm Complete Videolar"] --> SORT["Retention'a göre sırala"]
    SORT --> TOP["Top 5 → DO örnekleri<br/>✅ Neden iyi çalıştı?"]
    SORT --> BOT["Bottom 5 → DON'T örnekleri<br/>❌ Neden başarısız?"]
    TOP --> INJECT["Writer + Evaluator<br/>Prompt'larına enjekte"]
    BOT --> INJECT
```

---

## 📊 YouTube Analytics Entegrasyonu

### Dosya: `lambda/video_creator/youtube_analytics.py`

```mermaid
stateDiagram-v2
    [*] --> pending: Video üretildi
    pending --> linked: YouTube URL eklendi
    linked --> complete: Analytics çekildi (24-72 saat)
    linked --> failed: 72+ saat veri yok
    complete --> [*]: Decision Engine kullanır
    failed --> [*]
```

### Retry Stratejisi

| Video Yaşı | Aksiyon |
|------------|---------|
| < 24 saat | Atla (analytics hazır değil) |
| 24-72 saat | Dene, başarısızsa yarın tekrar |
| > 72 saat | Veri yoksa `failed` işaretle |

### DynamoDB — `shorts_video_metrics`

| Alan | Açıklama |
|------|----------|
| `video_id` | Benzersiz ID |
| `youtube_video_id` | YouTube video ID'si |
| `predicted_retention` | AI tahmini (%) |
| `actual_retention` | Gerçek YouTube değeri (%) |
| `hook_score` | Hook puanı (0-10) |
| `first_hook_score` 🆕 | Pre-refine hook skoru |
| `final_hook_score` 🆕 | Post-refine hook skoru |
| `refine_total` | Toplam refine sayısı |
| `status` | pending / linked / complete / failed |
| `calibration_eligible` | Kalibrasyon için uygun mu? |

---

## 🖥️ Admin Paneli & API

### Hosting: CloudFront + S3 (Terraform ile otomatik deploy)

### API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | /stats | Dashboard istatistikleri |
| GET | /videos | Video listesi (filtreli) |
| GET | /videos/{id} | Tek video detayı |
| PATCH | /videos/{id} | Video güncelle |
| DELETE | /videos/{id} | Video sil |
| POST | /videos/bulk | Toplu güncelleme (max 50) |
| POST | /generate | On-demand video üret |
| GET | /jobs | Son üretim işleri |
| GET | /jobs/{id} | İş detayı |
| GET | /logs | Yapısal loglar |

### Özellikler
- **Link Video**: YouTube URL ekle (otomatik ID parse)
- **Rate Limiting**: Dakikada 2 istek limiti
- **Idempotency**: `client_request_id` ile duplicate engelleme
- **Job Monitoring**: Real-time iş durumu ve loglar

---

## ☁️ AWS Altyapısı & Deployment

### Servis Haritası

```mermaid
graph TD
    subgraph COMPUTE["⚡ Compute"]
        L1["Video Generator Lambda"]
        L2["Analytics Fetcher Lambda"]
        L3["Decision Engine Lambda"]
        L4["Prompt Memory Lambda"]
        L5["Weekly Report Lambda"]
        L6["Admin API Lambda"]
    end

    subgraph STORAGE["💾 Storage"]
        S3["S3<br/>Video + Müzik + Admin Panel"]
        DDB1["DynamoDB<br/>shorts_video_metrics"]
        DDB2["DynamoDB<br/>shorts_jobs"]
        DDB3["DynamoDB<br/>shorts_run_logs"]
        DDB4["DynamoDB<br/>shorts_rate_limits"]
    end

    subgraph NETWORKING["🌐 Networking"]
        CF["CloudFront CDN"]
        APIGW["API Gateway"]
        SNS["SNS Topic"]
    end

    subgraph AI["🤖 AI"]
        BEDROCK["Bedrock<br/>Claude 3.5 + Titan"]
        POLLY["Polly<br/>Neural TTS"]
    end

    APIGW --> L1
    APIGW --> L6
    L1 --> S3
    L1 --> DDB1
    L1 --> BEDROCK
    L1 --> POLLY
    L2 --> DDB1
    L3 --> DDB1
    CF --> S3
    L1 --> SNS

    style AI fill:#e8f5e9,stroke:#333
    style COMPUTE fill:#fff3e0,stroke:#333
```

### EventBridge Zamanlamaları

| Lambda | Zamanlama | Açıklama |
|--------|-----------|----------|
| Video Generator | Her 8 saatte bir | Otomatik video üretimi |
| Analytics Fetcher | Her gün 23:00 UTC | YouTube verilerini çek |
| Decision Engine | Her gün 23:30 UTC | Autopilot ağırlıkları güncelle |
| Weekly Report | Pazar 20:00 UTC | Haftalık rapor |
| Prompt Memory | Pazar 21:00 UTC | DO/DON'T güncelle |

### Terraform Dosyaları

| Dosya | İçerik |
|-------|--------|
| `main.tf` | Provider, S3 video bucket, SNS |
| `lambda.tf` | Video Generator Lambda |
| `analytics_lambda.tf` | Analytics Fetcher Lambda |
| `autopilot_lambda.tf` | Decision Engine + Prompt Memory |
| `api_admin.tf` | API Gateway + Admin Lambda |
| `api_generate.tf` | /generate, /jobs, /logs API |
| `dynamodb_metrics.tf` | Video metrics tablosu |
| `dynamodb_jobs.tf` | Jobs, run_logs, rate_limits |
| `s3_admin_panel.tf` | Admin panel hosting |
| `iam.tf` | IAM rolleri ve politikaları |

### Kurulum

```powershell
# 1. Repo'yu klonla
git clone https://github.com/your-repo/historical-shorts.git
cd historical-shorts

# 2. Setup script'i çalıştır
.\setup.ps1    # Windows

# 3. Terraform deploy
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply

# 4. YouTube OAuth token (bir kerelik)
cd ..
python get_youtube_token.py
```

### Lambda Layer'ları

| Layer | İçerik |
|-------|--------|
| FFmpeg Layer | FFmpeg binary (video işleme) |
| Python Deps | requests, pydantic vb. bağımlılıklar |

---

## 🔧 Konfigürasyon

### Pipeline Ayarları (`script_pipeline.py`)

```python
# Quality Mode
QUALITY_MODE_CONFIG = {
    "hook_threshold": 9.0,
    "section_threshold": 8.5,
    "hook_max_iterations": 3,    # 2 refine
    "section_max_iterations": 2,  # 1 refine
    "max_api_calls": 30
}

# Dual Jury
SONNET_WEIGHT = 0.4
HAIKU_WEIGHT = 0.6
SONNET_FLOOR = 6.5
```

### Autopilot Safety Bounds (`decision_engine.py`)

```python
WEIGHT_BOUNDS = {
    "mode": {"QUALITY": (0.3, 0.9), "FAST": (0.1, 0.5)},
    "title": {"bold": (0.2, 0.8), "safe": (0.1, 0.6), "experimental": (0.05, 0.4)},
}

DECAY_WEIGHTS = {7: 1.0, 14: 0.5, 21: 0.25, 999: 0.1}
```

### Ortam Değişkenleri (Lambda)

| Değişken | Açıklama |
|----------|----------|
| `AWS_REGION_NAME` | AWS bölgesi (us-east-1) |
| `METRICS_TABLE_NAME` | DynamoDB video metrics tablosu |
| `JOBS_TABLE_NAME` | DynamoDB jobs tablosu |
| `VIDEO_BUCKET` | S3 video bucket adı |
| `YOUTUBE_SECRET_ARN` | YouTube OAuth secret ARN |
| `SNS_TOPIC_ARN` | Bildirim SNS topic ARN |

---

## 📈 Maliyet Tahmini

| Servis | Günlük ~3 video |
|--------|-----------------|
| Lambda | ~$0.50 |
| Bedrock Claude | ~$1.50 |
| Bedrock Titan | ~$0.40 |
| Polly | ~$0.10 |
| S3 + DynamoDB | ~$0.04 |
| CloudFront | ~$0.01 |
| **Toplam** | **~$2.55/gün** |

---

## 🐛 Sorun Giderme

| Problem | Çözüm |
|---------|-------|
| Video çok kısa | Klip sürelerini kontrol et (8 saniye olmalı) |
| Titan görsel üretmiyor | `titan_sanitizer.py` loglarını kontrol et |
| CORS hatası | API Gateway redeploy: `create-deployment` |
| Analytics çekilmiyor | YouTube OAuth token kontrol et |
| Decision Engine çalışmıyor | `status=complete` + `calibration_eligible=true` video olmalı |
| Admin panel 403/404 | CloudFront invalidation: `--paths "/*"` |
| Job durumu "queued" | Lambda timeout kontrol et, `shorts_run_logs` incele |
| Kalibrasyon raporu boş | Min 15 complete video gerekli |

---

## 📂 Dosya Yapısı

```
historical/
├── README.md
├── setup.ps1 / setup.sh
├── get_youtube_token.py
│
├── admin-panel/
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── lambda/
│   ├── layer/
│   │   ├── ffmpeg-layer.zip
│   │   └── python-deps.zip
│   │
│   ├── admin_api/
│   │   └── handler.py
│   │
│   └── video_creator/
│       ├── handler.py                 # Orchestrator + job tracking
│       ├── script_pipeline.py         # ⚖️ Dual Jury + Targeted Refine
│       ├── calibration_report.py      # 🔬 8-analiz kalibrasyon raporu
│       ├── topic_selector.py          # 🏄 History Buffet + Wave Surfing
│       ├── stock_fetcher.py           # 🎬 Visual Director
│       ├── titan_sanitizer.py         # Prompt güvenlik filtresi
│       ├── video_composer.py          # FFmpeg video render
│       ├── tts.py                     # AWS Polly TTS
│       ├── subtitle_gen.py            # Altyazı oluşturma
│       ├── music_fetcher.py           # S3'den müzik çekme
│       ├── smart_music_cutter.py      # Akıllı müzik kesimi
│       ├── story_music_matcher.py     # Mood-müzik eşleştirme
│       ├── sfx_generator.py           # Ses efektleri
│       ├── decision_engine.py         # 🎰 Thompson Sampling autopilot
│       ├── prompt_memory.py           # DO/DON'T hafıza
│       ├── weekly_report.py           # Haftalık performans raporu
│       ├── youtube_analytics.py       # YouTube API
│       ├── metrics_correlator.py      # Tahmin-gerçek karşılaştırma
│       ├── similarity_dampener.py     # Konu çeşitlilik kontrolü
│       ├── copyright_safety.py        # Telif hakkı takibi
│       ├── models.py                  # Data modeller
│       ├── utils/
│       │   └── analytics_score.py     # 📊 Virality Score
│       └── test_*.py                  # Test suites
│
├── terraform/                         # AWS altyapı (IaC)
│   ├── main.tf / lambda.tf / iam.tf / ...
│   └── autopilot_seed.json
│
└── tests/                             # Integration tests
```

---

*Son güncelleme: 2026-02-13 — Scientific Phase v2.4*
