# 🌙 YouTube Shorts AI Video Generator - Calm Life Edition

## 📋 Proje Özeti

Bu proje, tamamen otomatik **Calm Life / Night Wellness** YouTube Shorts videoları oluşturan bir AWS Lambda tabanlı sistemdir.

**Konsept:** "Sana bir şey öğretmiyorum. Sadece biraz yavaşlamana izin veriyorum."

Her gün otomatik olarak:
1. AI ile sakinleştirici senaryo oluşturur (AWS Bedrock Claude - whisper tone)
2. Senaryoya uygun huzurlu stok videolar indirir (Pexels API)
3. Yumuşak, yavaş seslendirme yapar (AWS Polly - %85-90 rate)
4. Ambient arka plan müziği üretir (FFmpeg synthesized)
5. Tüm içeriği birleştirip video üretir (no zoom, %5 slow-mo)
6. S3'e yükler ve e-posta bildirimi gönderir (SNS)

**TÜM İÇERİK TELİF HAKLARINDAN MUAFTİR** - Pexels lisansı veya AI-generated.

---

## 🏗️ Mimari

```
EventBridge (Günlük Zamanlayıcı)
        ↓
Lambda (video_generator)
        ↓
┌───────────────────────────────────────────────────┐
│  1. script_gen.py      → Bedrock Claude (whisper) │
│  2. stock_fetcher.py   → Pexels API (calm images) │
│  3. tts.py             → AWS Polly (soft voice)   │
│  4. music_fetcher.py   → FFmpeg (ambient tones)   │
│  5. subtitle_gen.py    → ASS format (minimal)     │
│  6. video_composer.py  → FFmpeg (no zoom)         │
│  7. copyright_safety.py → Lisans takibi           │
└───────────────────────────────────────────────────┘
        ↓
S3 (video storage) + SNS (e-mail notification)
```

---

## 🌙 Calm Life Konsept Detayları

### İçerik Ruhu
| ❌ Yapma | ✅ Yap |
|----------|--------|
| "Change your life" | "Maybe try this sometime" |
| "Fix your anxiety" | "Nothing is wrong with you" |
| "Do this now" | "Whenever you're ready" |
| Emir kipi | İzin veren dil |

### Video Formatı
- **Süre:** 8-11 saniye
- **Yapı:**
  1. Yumuşak soru (0-3s): "Mind feels loud?"
  2. İzin cümlesi (3-7s): "You don't have to fix everything tonight"
  3. Sessiz kapanış (7-10s): "Just breathe"

### Görsel Kimlik
- **Font:** Arial 60px, beyaz, hafif gölge
- **Müzik:** Ambient, %35 volume
- **Video:** Sabit kamera, %5 yavaşlatma, zoom yok
- **Renk:** Koyu mavi/gri tonları

---

## 📁 Dosya Yapısı

### `/lambda/video_creator/` - Lambda Kodu

| Dosya | Açıklama | Calm Life Özellikleri |
|-------|----------|----------------------|
| `script_gen.py` | Senaryo üretici | Whisper tone, 8-11s format |
| `stock_fetcher.py` | Video indirici | Calm imagery keywords |
| `tts.py` | Seslendirme | %85-90 rate, -8% pitch |
| `music_fetcher.py` | Müzik üretici | AAC/MP3/WAV fallback |
| `subtitle_gen.py` | Altyazı üretici | 60px, minimal style |
| `video_composer.py` | Video birleştirici | No zoom, 5% slow-mo |
| `handler.py` | Ana handler | Tüm adımları koordine eder |

---

## 🚀 Deploy Komutları

```powershell
# Terraform dizinine git
cd terraform

# Deploy et
terraform apply -auto-approve
```

## 🧪 Test Komutları

```powershell
# Manuel video oluşturma
aws lambda invoke --function-name youtube-shorts-video-generator --payload "{}" --region us-east-1 response.json; Get-Content response.json

# CloudWatch loglarını görüntüle
aws logs tail /aws/lambda/youtube-shorts-video-generator --region us-east-1 --since 10m
```

---

## 📊 Maliyet Tahmini (Aylık)

| Servis | Kullanım | Tahmini Maliyet |
|--------|----------|-----------------|
| Lambda | 30 çağrı × 2 dk | ~$0.08 |
| S3 | ~1GB video | ~$0.02 |
| Bedrock Claude | 30 istek | ~$0.50 |
| Polly | 30 seslendirme | ~$0.15 |
| SNS | 30 e-posta | Ücretsiz |
| **TOPLAM** | | **~$0.75/ay** |

---

## ✅ Durum (Son Güncelleme: 2026-01-26)

- [x] Lambda deployment çalışıyor
- [x] Script generation (whisper tone)
- [x] Video fetching (calm imagery)
- [x] TTS (soft voice, slow rate)
- [x] Music generation (ambient AAC/MP3/WAV)
- [x] Video composition (no zoom, slow-mo)
- [x] S3 upload
- [x] E-mail notification
- [x] Copyright tracking
- [x] Subtitle overlay (minimal style)
- [ ] Production verification

---

**Bu dosyayı güncel tut!** Yeni değişiklikler yapıldığında buraya ekle.
