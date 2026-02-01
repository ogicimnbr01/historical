<# 
.SYNOPSIS
    Setup script for YouTube Shorts AI Video Generator
.DESCRIPTION
    Creates FFmpeg and Python dependency layers for AWS Lambda
#>

Write-Host "YouTube Shorts AI - Setup" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LayerDir = Join-Path $ProjectDir "lambda\layer"

New-Item -ItemType Directory -Force -Path $LayerDir | Out-Null

Write-Host ""
Write-Host "Step 1: Creating FFmpeg layer..." -ForegroundColor Yellow

$FfmpegZip = Join-Path $LayerDir "ffmpeg-layer.zip"

if (-not (Test-Path $FfmpegZip)) {
    Write-Host "Downloading FFmpeg..."
    
    $TempDir = Join-Path $env:TEMP "ffmpeg_build"
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    
    $FfmpegUrl = "https://github.com/serverlesspub/ffmpeg-aws-lambda-layer/releases/download/v1.0.0/ffmpeg.zip"
    $DownloadPath = Join-Path $TempDir "ffmpeg.zip"
    
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $FfmpegUrl -OutFile $DownloadPath -UseBasicParsing
        Copy-Item $DownloadPath $FfmpegZip
        Write-Host "FFmpeg layer created" -ForegroundColor Green
    }
    catch {
        Write-Host "Could not download FFmpeg. Creating placeholder..." -ForegroundColor Yellow
        
        $binDir = Join-Path $TempDir "bin"
        New-Item -ItemType Directory -Force -Path $binDir | Out-Null
        "placeholder" | Out-File -FilePath (Join-Path $binDir "README.txt")
        
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($TempDir, $FfmpegZip)
    }
    
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}
else {
    Write-Host "FFmpeg layer already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Step 2: Creating Python deps layer..." -ForegroundColor Yellow

$PythonZip = Join-Path $LayerDir "python-deps.zip"

if (-not (Test-Path $PythonZip)) {
    $TempDir = Join-Path $env:TEMP "python_deps"
    $PythonDir = Join-Path $TempDir "python"
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
    
    pip install requests -t $PythonDir --quiet 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::CreateFromDirectory($TempDir, $PythonZip)
        Write-Host "Python deps layer created" -ForegroundColor Green
    }
    else {
        Write-Host "pip failed - make sure Python is installed" -ForegroundColor Red
    }
    
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}
else {
    Write-Host "Python deps layer already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "Step 3: Checking terraform.tfvars..." -ForegroundColor Yellow

$TfvarsFile = Join-Path $ProjectDir "terraform\terraform.tfvars"

if (Test-Path $TfvarsFile) {
    Write-Host "terraform.tfvars exists" -ForegroundColor Green
}
else {
    Write-Host "terraform.tfvars not found - create it manually" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Enable Claude 3 Opus in AWS Bedrock before deploying!" -ForegroundColor Yellow
Write-Host "AWS Console -> Bedrock -> Model Access -> Claude 3 Opus" -ForegroundColor White
Write-Host ""
Write-Host "Next: cd terraform && terraform init && terraform apply" -ForegroundColor White
