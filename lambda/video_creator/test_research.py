import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add lambda directory to path
sys.path.append(os.path.abspath("lambda/video_creator"))

try:
    from utils.researcher import get_wiki_summary  # pyre-ignore[21]

    def test_smart_search():
        # Difficult test case: Topic with no exact title match
        topic = "Spartans' brutal training"
        
        print(f"🧪 Testing Topic: {topic}")
        print("-" * 40)
        
        # This should trigger the fallback search
        summary = get_wiki_summary(topic)
        
        print("-" * 40)
        
        if summary:
            print("\n✅ TEST PASSED!")
            print(f"Preview: {summary[:100]}...")
            
            # Content check: Does it mention relevant terms?
            if "Sparta" in summary or "Agoge" in summary:
                print("✅ Content relevance confirmed.")
            else:
                print("⚠️ Content might not be relevant (check manually).")
        else:
            print("\n❌ TEST FAILED: No summary returned.")

    if __name__ == "__main__":
        test_smart_search()

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
