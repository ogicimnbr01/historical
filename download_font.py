import requests
import os

# URLs to try (Roboto or DejaVuSans)
urls = [
    "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Bold.ttf",
    "https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Bold.ttf",
    "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf",
    "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/DejaVuSans-Bold.ttf",
    "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf",
    "https://github.com/Haixing-Hu/latex-chinese-fonts/raw/master/english/Roboto-Bold.ttf"
]
dest = "lambda/video_creator/font.ttf"

for url in urls:
    print(f"Trying {url}...")
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(dest, 'wb') as f:
                f.write(response.content)
            print(f"Success! Font downloaded to {dest}")
            print(f"Size: {os.path.getsize(dest)} bytes")
            break
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
