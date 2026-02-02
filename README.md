# 🎬 History YouTube Shorts Generator

Automated AI-powered YouTube Shorts video generator focused on historical content. Creates engaging, viral-ready 15-second videos with AI-generated scripts, images, voiceover, and music.

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  EventBridge    │────▶│   Lambda         │────▶│   S3 Bucket     │
│  (Scheduler)    │     │  (Video Creator) │     │  (Videos/Audio) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌─────────┐ ┌─────────┐ ┌─────────┐
              │ Bedrock │ │  Titan  │ │  Polly  │
              │ (Claude)│ │ (Image) │ │  (TTS)  │
              └─────────┘ └─────────┘ └─────────┘
```

## 🚀 Features

### Content Generation
- **AI Script Generation** - Claude-powered historical storytelling
- **Hook Quality Control** - Blacklist/whitelist patterns for viral hooks
- **15s Guarantee** - Smart timing with poetic ending detection

### Video Production
- **AI Images** - Amazon Titan image generation
- **Text-to-Speech** - Amazon Polly with epic narrator voice
- **Dynamic Music** - Context-aware background music with climax
- **Event SFX** - Sword, cannon, wave sounds based on content
- **Animated Subtitles** - Word-by-word reveal with effects

### Content Variety
- **Similarity Dampener** - Prevents repetitive content across videos
- **Dynamic Thresholds** - Adapts to history count
- **Family-based Patterns** - Hook and ending style variation

## 📁 Project Structure

```
historical/
├── terraform/           # Infrastructure as Code
│   ├── main.tf
│   ├── lambda.tf
│   ├── s3.tf
│   └── eventbridge.tf
│
└── lambda/
    └── video_creator/
        ├── main.py              # Lambda handler
        ├── script_gen.py        # AI script generation
        ├── video_composer.py    # FFmpeg video assembly
        ├── subtitle_gen.py      # ASS subtitle creation
        ├── audio_gen.py         # TTS & music generation
        └── similarity_dampener.py  # Content variety system
```

## 🛠️ Setup

### Prerequisites
- AWS CLI configured
- Terraform installed
- Python 3.11+

### Deployment

```bash
cd historical/terraform
terraform init
terraform apply
```

### Manual Invocation

```bash
# Async invoke (recommended)
aws lambda invoke \
  --function-name youtube-shorts-video-generator \
  --payload "{}" \
  --invocation-type Event \
  --region us-east-1 \
  response.json
```

## 📊 Similarity Dampener

Prevents content repetition across videos:

| Pattern Type | Threshold | Action |
|--------------|-----------|--------|
| Hook | 30% of last N | BAN |
| Ending | 20% / 30% | PENALIZE / BAN |
| Break Line | 30% of last N | BAN |

**Dynamic Features:**
- `MIN_HISTORY_FOR_BAN = 4` - No bans with < 4 videos
- `escape_hatch` - Allows pattern rewriting when stuck
- ISO timestamp sorting for deterministic history

## 🎯 Hook Patterns

### Blacklisted (Weak)
- "Did you know..."
- "Today we'll learn..."
- "Have you ever wondered..."

### Whitelisted (Strong)
- `contradiction`: "X was a lie" / "This never happened"
- `revelation`: "The truth is..." / "History lied about X"
- `challenge`: "Everyone remembers this wrong"
- `contrast`: "He conquered X, but..."

## 📈 Monitoring

Watch these CloudWatch metrics after deployment:

| Metric | Healthy Range | Alert If |
|--------|---------------|----------|
| `escape_hatch_used` | ≤ 10% | > 25% |
| `hook_ban_rate` | ≤ 20% | > 40% |
| `ending_penalize_rate` | ≤ 30% | > 50% |

## 🔧 Configuration

Environment variables (set in `terraform.tfvars`):

```hcl
aws_region     = "us-east-1"
s3_bucket_name = "youtube-shorts-videos"
schedule       = "rate(6 hours)"
```

## 📝 License

Private project - All rights reserved.
