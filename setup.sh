#!/bin/bash
# Setup script for YouTube Shorts AI Video Generator
# Run this script before terraform apply

set -e

echo "🚀 YouTube Shorts AI - Setup Script"
echo "===================================="

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAYER_DIR="$PROJECT_DIR/lambda/layer"

# Create layer directory
mkdir -p "$LAYER_DIR"

echo ""
echo "📦 Step 1: Creating FFmpeg layer..."
echo "-----------------------------------"

cd "$LAYER_DIR"

# Download FFmpeg static build
if [ ! -f "ffmpeg-layer.zip" ]; then
    echo "Downloading FFmpeg static build..."
    curl -L "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz" -o ffmpeg.tar.xz
    
    # Extract
    tar -xf ffmpeg.tar.xz
    
    # Create layer structure
    mkdir -p bin
    cp ffmpeg-*-amd64-static/ffmpeg bin/
    cp ffmpeg-*-amd64-static/ffprobe bin/
    chmod +x bin/*
    
    # Create zip
    zip -r ffmpeg-layer.zip bin/
    
    # Cleanup
    rm -rf ffmpeg-*-amd64-static ffmpeg.tar.xz bin/
    
    echo "✅ FFmpeg layer created: ffmpeg-layer.zip"
else
    echo "✅ FFmpeg layer already exists"
fi

echo ""
echo "📦 Step 2: Creating Python dependencies layer..."
echo "-------------------------------------------------"

if [ ! -f "python-deps.zip" ]; then
    # Create temp directory for pip packages
    TEMP_DIR=$(mktemp -d)
    mkdir -p "$TEMP_DIR/python"
    
    echo "Installing Python packages..."
    pip install openai requests -t "$TEMP_DIR/python" --quiet
    
    # Create zip
    cd "$TEMP_DIR"
    zip -r "$LAYER_DIR/python-deps.zip" python/
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    
    echo "✅ Python deps layer created: python-deps.zip"
else
    echo "✅ Python deps layer already exists"
fi

cd "$PROJECT_DIR"

echo ""
echo "📝 Step 3: Check terraform.tfvars..."
echo "------------------------------------"

TFVARS_FILE="$PROJECT_DIR/terraform/terraform.tfvars"
TFVARS_EXAMPLE="$PROJECT_DIR/terraform/terraform.tfvars.example"

if [ ! -f "$TFVARS_FILE" ]; then
    echo "⚠️  terraform.tfvars not found!"
    echo "   Copy the example and fill in your values:"
    echo "   cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
    echo ""
    echo "   Required values:"
    echo "   - openai_api_key     (from https://platform.openai.com)"
    echo "   - pexels_api_key     (from https://www.pexels.com/api/)"
    echo "   - notification_email (your email for alerts)"
else
    echo "✅ terraform.tfvars exists"
fi

echo ""
echo "🎉 Setup complete!"
echo "=================="
echo ""
echo "Next steps:"
echo "1. Edit terraform/terraform.tfvars with your API keys"
echo "2. cd terraform"
echo "3. terraform init"
echo "4. terraform plan"
echo "5. terraform apply"
echo ""
