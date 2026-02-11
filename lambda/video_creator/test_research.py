import sys
import os

# Add lambda directory to path
sys.path.append(os.path.abspath("lambda/video_creator"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

try:
    from utils.researcher import get_wiki_summary  # pyre-ignore[21]
    print("Testing researcher...")
    summary = get_wiki_summary("Suleiman the Magnificent")
    if summary:
        print(f"✅ Success! Summary length: {len(summary)}")
        print(f"Start: {summary[:100]}...")
    else:
        print("❌ Failed to fetch summary")
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
