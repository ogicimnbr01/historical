# 🎬 YouTube Shorts AI Video Generator

**Tam otomatik YouTube Shorts video üretim sistemi**

Tarihsel içerikler için AI destekli video üretimi yapar. Senaryo yazımından video render'ına, kalite skorlamasından YouTube Analytics takibine kadar tüm süreç otomatiktir.

---

## 📋 İçindekiler

1. [Sistem Genel Bakış](#-sistem-genel-bakış)
2. [Nasıl Çalışır?](#-nasıl-çalışır)
3. [Senaryo Üretimi ve Puanlama](#-senaryo-üretimi-ve-puanlama)
4. [Görsel Üretimi (Titan AI)](#-görsel-üretimi-titan-ai)
5. [Ses Üretimi (AWS Polly)](#-ses-üretimi-aws-polly)
6. [Müzik Sistemi](#-müzik-sistemi)
7. [Video Kompozisyonu (FFmpeg)](#-video-kompozisyonu-ffmpeg)
8. [YouTube Analytics Entegrasyonu](#-youtube-analytics-entegrasyonu)
9. [Admin Paneli](#-admin-paneli)
10. [AWS Altyapısı](#-aws-altyapısı)
11. [Kurulum](#-kurulum)
12. [Dosya Yapısı](#-dosya-yapısı)

---

## 🌟 Sistem Genel Bakış

Bu sistem tamamen **serverless** (sunucusuz) bir mimaride çalışır:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AWS Cloud                                        │
│                                                                          │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│           Video Generator Lambda             │   │
│  │  (Scheduler) │    │  • Senaryo üret (Claude)                     │   │
│  │  Her 8 saat  │    │  • Görsel üret (Titan)                       │   │
│  └──────────────┘    │  • Ses üret (Polly)                          │   │
│                      │  • Video birleştir (FFmpeg)                   │   │
│                      └──────────────┬───────────────────────────────┘   │
│                                     │                                    │
│                                     ▼                                    │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │      S3      │◀───│              Video & Metadata                 │   │
│  │   (Storage)  │    └──────────────────────────────────────────────┘   │
│  └──────────────┘                                                        │
│                                                                          │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │  EventBridge │───▶│         Analytics Fetcher Lambda              │   │
│  │  (23:00 UTC) │    │  • YouTube'dan gerçek retention çek          │   │
│  └──────────────┘    │  • Tahminlerle karşılaştır                   │   │
│                      └──────────────┬───────────────────────────────┘   │
│                                     │                                    │
│                                     ▼                                    │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │   DynamoDB   │◀───│          Video Metrics Database               │   │
│  │  (Database)  │    └──────────────────────────────────────────────┘   │
│  └──────────────┘                                                        │
│                                                                          │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │ API Gateway  │───▶│            Admin API Lambda                   │   │
│  │  (REST API)  │    │  • Video listele/düzenle/sil                  │   │
│  └──────────────┘    │  • YouTube link'le                            │   │
│                      │  • İstatistikler                              │   │
│                      └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Nasıl Çalışır?

### Video Üretim Akışı (Adım Adım)

```
1. BAŞLA
   │
   ▼
2. KONU SEÇ (rastgele tarihsel konu)
   │
   ▼
3. SENARYO YAZDIR (Claude AI)
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
4. KPI TAHMİN ET
   │  • Instant Clarity (hemen anlaşılıyor mu?)
   │  • Curiosity Gap (merak uyandırıyor mu?)
   │  • Swipe Risk (kaydırma riski)
   │  • Predicted Retention (tahmini izlenme %)
   │
   ▼
5. GÖRSEL ÜRET (4 adet AI görsel - Titan)
   │  • Her segment için ayrı görsel
   │  • Ken Burns efekti (zoom/pan)
   │  • Tarihe uygun film grain
   │
   ▼
6. SESLENDİRME ÜRET (AWS Polly)
   │  • Belgesel tarzı erkek ses
   │  • Türkçe/yabancı isimleri fonetik yaz
   │
   ▼
7. MÜZİK SEÇ ve KES
   │  • Mood'a uygun müzik (epic, emotional, etc.)
   │  • En iyi segmenti bul ve kes
   │
   ▼
8. FFmpeg ile BİRLEŞTİR
   │  • 1080x1920 (9:16 vertical)
   │  • Altyazı ekle
   │  • Ses + müzik + SFX miksle
   │  • Film grain efekti
   │
   ▼
9. S3'e YÜKLE + DynamoDB'ye KAYDET
   │
   ▼
10. SNS ile BİLDİRİM GÖNDER
    │
    ▼
11. BİTTİ! ✅
```

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

## 🎨 Görsel Üretimi (Titan AI)

### Dosya: `lambda/video_creator/stock_fetcher.py`

AWS Bedrock Titan Image Generator kullanarak tarihi görseller üretir.

### Güvenlik Filtresi (Titan Sanitizer)

AWS Titan bazı içerikleri engeller:
- Şiddet/savaş sahneleri
- Ünlü kişilerin yüzleri
- Nefret söylemi

Bu yüzden **titan_sanitizer.py** prompt'ları güvenli hale getirir:

```python
# Örnek dönüşümler
"war" → "soldiers in marching formation"
"battle" → "heroic warrior stance"
"Genghis Khan" → "13th century Mongol emperor in golden armor"
"blood" → "crimson sunset"
```

### Ken Burns Efekti

Her görsel 8 saniyelik videoya dönüşür:
- Yavaş zoom in/out
- Hafif pan (yatay hareket)
- Fade in başlangıç
- Film grain efekti (dönemine göre)

```python
# stock_fetcher.py - Her klip 8 saniye üretilir
'-t', '8',  # 8 second clip (supports voiceovers up to 32s with 4 clips)
```

### Fallback Sistemi

Titan başarısız olursa:
1. **Önceki başarılı görseli kullan** (varsa)
2. **Gradient fallback** - dönemine uygun renk geçişi oluştur

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
```

### DynamoDB'de Saklanan Bilgiler

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

## 🖥️ Admin Paneli

### Dosyalar:
- `admin-panel/index.html` - Ana sayfa
- `admin-panel/app.js` - JavaScript logic
- `admin-panel/styles.css` - Stiller

### API Endpoints (Admin Lambda)

| Method | Endpoint         | Açıklama                    |
|--------|------------------|-----------------------------|
| GET    | /stats           | Dashboard istatistikleri    |
| GET    | /videos          | Video listesi (filtreli)    |
| GET    | /videos/{id}     | Tek video detayı            |
| PATCH  | /videos/{id}     | Video güncelle              |
| DELETE | /videos/{id}     | Video sil                   |
| POST   | /videos/bulk     | Toplu güncelleme            |

### Özellikler

- **Filtreleme**: Status, eligible, mode, pipeline
- **Link Video**: YouTube URL'si ekle
- **Mark as TEST**: Kalibrasyondan çıkar
- **Delete**: Test videolarını sil
- **Bulk Actions**: Çoklu seçim ve güncelleme

---

## ☁️ AWS Altyapısı

### Terraform Dosyaları

| Dosya                  | İçerik                              |
|-----------------------|-------------------------------------|
| main.tf               | Provider, S3 bucket, SNS            |
| lambda.tf             | Video Generator Lambda              |
| analytics_lambda.tf   | Analytics Fetcher Lambda            |
| api_admin.tf          | API Gateway + Admin Lambda          |
| dynamodb_metrics.tf   | DynamoDB tablosu                    |
| iam.tf                | IAM rolleri ve politikaları         |
| secrets.tf            | Secrets Manager referansları        |

### AWS Servisleri

| Servis              | Kullanım                           |
|---------------------|-------------------------------------|
| Lambda              | Video üretimi, analytics, admin API |
| S3                  | Video, müzik, görseller             |
| DynamoDB            | Video metrikleri veritabanı         |
| API Gateway         | Admin panel REST API                |
| EventBridge         | Zamanlanmış tetikleyiciler          |
| Bedrock (Claude)    | Senaryo yazımı ve puanlama          |
| Bedrock (Titan)     | AI görsel üretimi                   |
| Polly               | Text-to-Speech                      |
| SNS                 | Bildirimler                         |
| Secrets Manager     | YouTube OAuth credentials           |
| CloudWatch          | Loglar                              |

---

## 🚀 Kurulum

### Öngereksinimler

1. **AWS CLI** yapılandırılmış
2. **Terraform** kurulu
3. **Python 3.11+** kurulu
4. **Node.js** (admin panel için)

### Adımlar

```powershell
# 1. Repo'yu klonla
git clone https://github.com/your-repo/historical-shorts.git
cd historical-shorts

# 2. Terraform değişkenlerini ayarla
cd terraform
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars dosyasını düzenle

# 3. Terraform ile deploy et
terraform init
terraform apply

# 4. YouTube OAuth token al (bir kerelik)
cd ..
python get_youtube_token.py

# 5. Admin paneli çalıştır (local)
cd admin-panel
python -m http.server 8080
# Tarayıcıda http://localhost:8080 aç
```

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
├── README.md                 # Bu dosya
├── admin-panel/              # Web admin paneli
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
├── lambda/                   # Lambda fonksiyonları
│   ├── admin_api/
│   │   └── handler.py       # Admin API handler
│   │
│   └── video_creator/       # Ana video üretim modülü
│       ├── handler.py       # Ana Lambda handler (orchestrator)
│       ├── script_pipeline.py   # Senaryo + puanlama sistemi
│       ├── script_gen.py        # Legacy senaryo generator
│       ├── stock_fetcher.py     # Titan AI görsel üretimi
│       ├── titan_sanitizer.py   # Prompt güvenlik filtresi
│       ├── video_composer.py    # FFmpeg video birleştirme
│       ├── tts.py               # AWS Polly ses üretimi
│       ├── subtitle_gen.py      # Altyazı oluşturma
│       ├── music_fetcher.py     # S3'den müzik çekme
│       ├── smart_music_cutter.py # Akıllı müzik kesimi
│       ├── story_music_matcher.py # Mood-müzik eşleştirme
│       ├── sfx_generator.py     # Ses efektleri
│       ├── youtube_analytics.py # YouTube API entegrasyonu
│       ├── metrics_correlator.py # Tahmin-gerçek karşılaştırma
│       ├── similarity_dampener.py # Konu çeşitliliği kontrolü
│       └── copyright_safety.py  # Telif hakkı takibi
│
├── terraform/               # AWS altyapı tanımları
│   ├── main.tf
│   ├── lambda.tf
│   ├── analytics_lambda.tf
│   ├── api_admin.tf
│   ├── dynamodb_metrics.tf
│   ├── iam.tf
│   └── ...
│
└── tests/                   # Test dosyaları
```

---

## 🔧 Konfigürasyon

### Ortam Değişkenleri (Lambda)

| Değişken            | Açıklama                        |
|---------------------|---------------------------------|
| AWS_REGION_NAME     | AWS bölgesi (us-east-1)         |
| METRICS_TABLE_NAME  | DynamoDB tablo adı              |
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

---

## 📈 Maliyet Tahmini

| Servis         | Günlük ~3 video için |
|----------------|----------------------|
| Lambda         | ~$0.50               |
| Bedrock Claude | ~$1.50               |
| Bedrock Titan  | ~$0.40               |
| Polly          | ~$0.10               |
| S3             | ~$0.02               |
| DynamoDB       | ~$0.01               |
| **Toplam**     | **~$2.50/gün**       |

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

---

## 📞 Destek

Sorular için issue açabilirsiniz.

---

*Son güncelleme: 2026-02-05*
