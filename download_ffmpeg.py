import requests  # pyre-ignore[21]
import os
import zipfile
import shutil
import io

# URLs to try
# Using John Van Sickle release build (smaller size)
urls = [
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
]
layer_zip = "lambda/layer/ffmpeg-layer.zip"
bin_dir = "lambda/layer/bin"

for url in urls:
    print(f"Trying {url}...")
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            print(f"Success! Downloading from {url}...")
            
            # Create bin directory
            if os.path.exists(bin_dir):
                shutil.rmtree(bin_dir)
            os.makedirs(bin_dir)
            
            # Save tar file
            tar_path = "ffmpeg.tar.xz"
            with open(tar_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Extract tar content
            print("Extracting...")
            import tarfile
            with tarfile.open(tar_path, "r:xz") as tar:
                # Find ffmpeg binary
                ffmpeg_member = next((m for m in tar.getmembers() if m.name.endswith("/ffmpeg")), None)
                if ffmpeg_member:
                    ffmpeg_member.name = "ffmpeg" # Flatten
                    tar.extract(ffmpeg_member, path=bin_dir)
                
                # Find ffprobe binary
                ffprobe_member = next((m for m in tar.getmembers() if m.name.endswith("/ffprobe")), None)
                if ffprobe_member:
                    ffprobe_member.name = "ffprobe" # Flatten
                    tar.extract(ffprobe_member, path=bin_dir)

            # Check what we got
            print(f"Extracted files: {os.listdir(bin_dir)}")
            
            # Create Layer Zip
            print(f"Creating {layer_zip}...")
            if os.path.exists(layer_zip):
                os.remove(layer_zip)
                
            with zipfile.ZipFile(layer_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                if os.path.exists(os.path.join(bin_dir, "ffmpeg")):
                    zf.write(os.path.join(bin_dir, "ffmpeg"), "bin/ffmpeg")
                if os.path.exists(os.path.join(bin_dir, "ffprobe")):
                    zf.write(os.path.join(bin_dir, "ffprobe"), "bin/ffprobe")
                
            print("Layer zip created successfully!")
            
            # Cleanup
            if os.path.exists(tar_path):
                os.remove(tar_path)
            shutil.rmtree(bin_dir)
            break
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
