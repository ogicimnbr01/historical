# FFmpeg Lambda Layer

Bu klasör FFmpeg binary'sini içeren Lambda layer zip dosyasını içerir.

## Layer Oluşturma

FFmpeg layer'ı oluşturmak için aşağıdaki adımları takip edin:

### Option 1: Hazır Layer Kullan (Önerilen)

AWS Lambda için optimize edilmiş FFmpeg layer'ı indir:

```bash
# Linux/WSL üzerinde çalıştır
mkdir -p bin
cd bin

# FFmpeg static build indir
curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
tar -xf ffmpeg.tar.xz
mv ffmpeg-*-amd64-static/ffmpeg .
mv ffmpeg-*-amd64-static/ffprobe .
rm -rf ffmpeg-*-amd64-static ffmpeg.tar.xz

cd ..
zip -r ffmpeg-layer.zip bin/
```

### Option 2: Docker ile Oluştur

```bash
docker run --rm -v $(pwd):/output amazonlinux:2023 bash -c "
    yum install -y xz tar
    curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz
    mkdir -p /output/bin
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp
    cp /tmp/ffmpeg-*-amd64-static/ffmpeg /output/bin/
    cp /tmp/ffmpeg-*-amd64-static/ffprobe /output/bin/
    chmod +x /output/bin/*
"
zip -r ffmpeg-layer.zip bin/
```

## Layer Boyutu

- FFmpeg + FFprobe: ~80MB (sıkıştırılmış ~30MB)
- Lambda Layer limiti: 250MB (extracted)

## Notlar

- Layer'ı oluşturduktan sonra `ffmpeg-layer.zip` dosyasının bu klasörde olduğundan emin ol
- Terraform bu zip dosyasını Lambda layer olarak yükleyecek
