# 🎬 History Shorts: Otomatik YouTube Shorts Üretim Sistemi

## Bu Proje Ne Yapıyor?

**History Shorts**, tamamen otomatik çalışan bir YouTube Shorts video üretim sistemidir. Sistem, tarihi konularda ilgi çekici 15 saniyelik videolar üretir ve bunları belirlenen zaman aralıklarında otomatik olarak oluşturur.

Bir kez deploy ettikten sonra sistem kendi başına çalışır:
1. Tarihi bir konu seçer
2. Viral hook'lu bir script yazar
3. AI ile görseller üretir
4. Profesyonel seslendirme ekler
5. Arka plan müziği ve ses efektleri koyar
6. Animasyonlu altyazı ekler
7. Hepsini birleştirip video dosyası oluşturur

---

## 🎯 Amaç

YouTube Shorts, TikTok ve Instagram Reels gibi kısa video platformlarında organik büyüme elde etmek için **tutarlı ve kaliteli içerik üretimi** şart. Ancak:

- Her gün video üretmek zaman alıcı
- Editör tutmak pahalı
- İçerik fikirleri tükeniyor
- Kalite tutarsız oluyor

Bu sistem bu sorunları çözüyor:

| Problem | Çözüm |
|---------|-------|
| Zaman | Tamamen otomatik, 0 manuel iş |
| Maliyet | AWS serverless = kullandığın kadar öde |
| Fikir | AI rastgele tarihi konular seçiyor |
| Kalite | Editoryal kurallar kodlanmış |

---

## 🧠 Nasıl Çalışıyor?

### 1. Script Üretimi (Claude AI)
Amazon Bedrock üzerinde Claude modeli, şu kurallara göre script yazar:

**15 Saniye = 4 Bölüm:**
- **HOOK (0-3s)**: İzleyiciyi durduran şok cümle
- **CONTEXT (3-7s)**: Tarihi bağlam
- **FACT (7-12s)**: Şaşırtıcı bilgi
- **OUTRO (12-15s)**: Akılda kalıcı kapanış

**Kalite Kontrolleri:**
- Zayıf hook'lar yasaklı ("Did you know...", "Today we'll learn...")
- Güçlü hook'lar teşvik ediliyor ("X was a lie", "History got this wrong")
- 8-9 kelime = ideal hook uzunluğu
- 35-60 kelime = ideal toplam süre

### 2. Görsel Üretimi (Amazon Titan)
Her bölüm için AI görsel üretilir:
- 1024x1024 boyut → 9:16 dikey kırpılır
- Döneme uygun stil (yağlı boya, vintage fotoğraf, vb.)
- Tarihi figürün adı prompt'a dahil

### 3. Seslendirme (Amazon Polly)
- **Matthew** sesi (derin, dramatik erkek)
- Storyteller modu (epik anlatım)
- SSML ile tempo ve vurgu kontrolü

### 4. Müzik ve Ses Efektleri
**Arka Plan Müziği:**
- Dönem ve konuya göre stil seçimi
- Outro'da volume artışı (climax efekti)

**Event-based SFX:**
- Script'te "sword" geçiyorsa → kılıç sesi
- "cannon" geçiyorsa → top sesi
- "ship" geçiyorsa → dalga sesi

### 5. Altyazı Sistemi
- ASS formatı (advanced styling)
- Kelime kelime reveal animasyonu
- Hook = altın renk, büyük font
- Outro = italik, poetic stil

### 6. Video Birleştirme (FFmpeg)
- Tüm parçalar tek videoda
- Ken Burns efekti (zoom/pan)
- Smooth geçişler
- 1080x1920 (9:16) çıktı

---

## 🔄 Similarity Dampener: Tekrar Önleme Sistemi

50-60 video sonra içerikler birbirine benzemeye başlar. Bunu önlemek için **Similarity Dampener** sistemi var:

### Nasıl Çalışıyor?

1. **Her video üretildiğinde** → S3'e metadata kaydedilir:
   - Hangi hook pattern kullanıldı
   - Hangi ending style seçildi
   - Hangi break line eklendi

2. **Yeni video üretilmeden önce** → Son 10 video analiz edilir:
   - "was a lie" 3 kez mi kullanılmış? → YASAKLA
   - "legends lie" 2 kez mi kullanılmış? → UYAR
   - Hangi pattern'lar az kullanılmış? → ÖNERİ

3. **Claude'a kurallar iletilir:**
   ```
   🚫 BANNED HOOKS: was a lie, never happened
   ✅ USE THESE: revelation: "The truth is..."
   ```

### Dinamik Eşikler

İlk 4 videodan önce agresif yasaklama yapılmaz:
- n < 4 → Sadece uyarı, yasak yok
- n ≥ 4 → Tam sistem aktif

---

## 🏗️ Teknik Altyapı

### AWS Servisleri

| Servis | Kullanım |
|--------|----------|
| **Lambda** | Ana video üretim fonksiyonu |
| **S3** | Video, ses, görsel depolama |
| **EventBridge** | Zamanlanmış tetikleme |
| **Bedrock** | Claude (script) + Titan (görsel) |
| **Polly** | Text-to-speech |

### Terraform ile IaC

Tüm altyapı kod olarak tanımlı:
```bash
cd terraform
terraform init
terraform apply
```

Tek komutla tüm sistem kurulur/güncellenir.

---

## 💰 Maliyet

Tahmini maliyet (video başına):

| Kaynak | Maliyet |
|--------|---------|
| Lambda | ~$0.01 |
| Bedrock (Claude) | ~$0.02 |
| Bedrock (Titan) | ~$0.08 |
| Polly | ~$0.004 |
| S3 | ~$0.001 |
| **TOPLAM** | **~$0.12/video** |

Günde 4 video = ~$15/ay

---

## 📈 Gelecek Planları

| Versiyon | Özellik |
|----------|---------|
| v4 | A/B Hook Variant - 2 hook üret, en iyisini seç |
| v5 | Break family-based ban - Eş anlamlı kaçakları yakala |
| v6 | YouTube API entegrasyonu - Otomatik yükleme |
| v7 | Performance feedback - Hangi hook'lar iyi çalışıyor? |

---

## 🎯 Sonuç

Bu sistem, YouTube Shorts için **ölçeklenebilir, tutarlı, yüksek kaliteli** içerik üretimini otomatikleştirir. 

Manuel iş: **Sıfır**
Günlük çaba: **Sadece CloudWatch'a bakmak**
Çıktı: **İstediğin kadar video**

Tek yapman gereken `terraform apply` ve beklemek. 🚀
