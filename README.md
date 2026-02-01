# 🎬 AI YouTube Shorts Generator

Otomatik absürt, dopamin-patlatıcı YouTube Shorts videoları üreten AWS serverless sistem.

## ✨ Özellikler

- ✅ **Haftada 4 video** otomatik üretim
- ✅ **AWS Bedrock (Claude 3.5)** ile absürt senaryo üretimi
- ✅ **Pixabay** ücretsiz stock videolar (API key gerekmez!)
- ✅ **AWS Polly** doğal İngilizce seslendirme
- ✅ **FFmpeg** ile video montaj
- ✅ **Email bildirimi** video hazır olunca

## 💰 Maliyet

| Servis | Aylık (~16 video) |
|--------|-------------------|
| AWS Bedrock (Claude) | ~$0.50 |
| AWS Polly | ~$0.03 |
| AWS Lambda | Free tier |
| AWS S3 | ~$0.05 |
| **Toplam** | **~$0.60/ay** |

✅ $50 ile **6+ yıl** kullanım!

## 🚀 Kurulum

### Gereksinimler

- AWS CLI yapılandırılmış (`aws configure`)
- Terraform >= 1.0
- Python 3.11+
- **Bedrock Model Access** etkinleştirilmiş (Claude için)

### 1. Bedrock Erişimini Aç

AWS Console → Bedrock → Model Access → Claude 3.5 Sonnet'i etkinleştir.

### 2. Setup Script'i Çalıştır

```powershell
cd "shorts"
.\setup.ps1
```

### 3. Email Adresini Gir

```powershell
notepad terraform\terraform.tfvars
```

```hcl
notification_email = "your-email@example.com"
aws_region         = "us-east-1"
```

### 4. Deploy

```powershell
cd terraform
terraform init
terraform plan
terraform apply
```

### 5. Email Doğrulama

SNS subscription email'ini onayla.

## 📁 Proje Yapısı

```
shorts/
├── terraform/           # AWS altyapısı
│   ├── main.tf         # S3, SNS, EventBridge
│   ├── lambda.tf       # Lambda function
│   ├── iam.tf          # IAM (Bedrock, Polly, S3, SNS)
│   └── variables.tf
│
├── lambda/video_creator/
│   ├── handler.py       # Ana orchestrator
│   ├── script_gen.py    # Bedrock Claude senaryo
│   ├── stock_fetcher.py # Pixabay stock video
│   ├── tts.py           # AWS Polly TTS
│   └── video_composer.py# FFmpeg montaj
│
└── setup.ps1            # Windows setup
```

## ⏰ Video Zamanlaması

- Pazartesi 13:00 (TR)
- Çarşamba 13:00
- Cuma 13:00
- Pazar 13:00

## 🔧 Manuel Test

```powershell
# Lambda'yı manuel tetikle
aws lambda invoke `
  --function-name youtube-shorts-video-generator `
  --payload '{}' `
  response.json

# Logları izle
aws logs tail /aws/lambda/youtube-shorts-video-generator --follow
```

## 📧 Video Gelince

1. Email'deki link ile videoyu indir
2. YouTube Studio → Create → Upload Short
3. Yayınla! 🚀

## 🛑 Sistemi Durdurma

```powershell
cd terraform
terraform destroy
```
