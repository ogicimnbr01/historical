# 📋 CALM LIFE / NIGHT WELLNESS - TÜM YAPILACAKLAR

> **Son Güncelleme:** 2026-01-26 18:40
> **Proje:** YouTube Shorts otomatik video üretici (Calm Life / Night Wellness)
> **Konsept:** "Modern insanın yorgun zihnine izin veren içerik"

---

## 🎯 PROJE DURUMU

**Çalışan:**
- ✅ Lambda deployment
- ✅ Claude script generation (whisper/calm tone)
- ✅ Pexels video fetching (calm imagery)
- ✅ AWS Polly TTS (soft female voices: 85-90% rate)
- ✅ FFmpeg video composition (no zoom, 5% slow-mo)
- ✅ S3 upload + email notification
- ✅ Ambient music generation (AAC/MP3/WAV fallback)
- ✅ Minimal subtitle styling (60px, white, fade)

**Konsept Değişikliği (2026-01-26):**
- ✅ Fitness → Calm Life migrasyonu tamamlandı
- ✅ SYSTEM_PROMPT fısıltı tonuna geçti
- ✅ 15s → 8-11s format
- ✅ Zoom efektleri kaldırıldı
- ✅ Müzik %55 → %35'e düşürüldü

---

## 🌙 YENİ KONSEPT: CALM LIFE

### İçerik Ruhu
- ❌ "Bunu yapmalısın" → ✅ "Bazen şunu denemek iyi geliyor"
- ❌ "Fix your anxiety" → ✅ "Nothing is wrong with you"
- ❌ Emir kipi → ✅ İzin veren dil

### Video Yapısı (15 saniye)
1. **Derin açılış** (0-3s): Spesifik yaşanmış an
2. **Farkındalık** (3-6s): Ne olduğunu nazikçe adlandır
3. **İzin** (6-10s): Nefes aldıran mesaj
4. **Fiziksel ipucu** (10-13s): Bedeni toprakla
5. **Nazik CTA** (13-15s): Kaydet daveti

### Görsel Kimlik
- Font: Arial 60px, beyaz, hafif gölge
- Müzik: Ambient, %35 volume
- Video: Sabit kamera, %5 yavaşlatma
- Pexels bulamazsa: AI üretim (Bedrock Titan)

---

## 📁 DOSYA HARİTASI

| Dosya | Ne Yapar |
|-------|----------|
| `script_gen.py` | Claude ile calm script üret (whisper tone) |
| `stock_fetcher.py` | Pexels'tan calm imagery indir |
| `tts.py` | AWS Polly soft seslendirme (%85-90 rate) |
| `music_fetcher.py` | Ambient müzik üret (AAC/MP3/WAV) |
| `video_composer.py` | FFmpeg ile birleştir (no zoom) |
| `subtitle_gen.py` | Minimal ASS altyazı (60px) |
| `handler.py` | Lambda ana fonksiyon |

---

## 🔧 DEPLOY KOMUTLARI

```powershell
cd c:\Users\oguzb\OneDrive\Masaüstü\deneme projeler\shorts\terraform
terraform apply -auto-approve
```

```powershell
aws lambda invoke --function-name youtube-shorts-video-generator --payload "{}" --region us-east-1 response.json; Get-Content response.json
```

```powershell
aws logs tail /aws/lambda/youtube-shorts-video-generator --region us-east-1 --since 10m
```

---

**Bu dosyayı koru! Tüm bilgiler burada.**
