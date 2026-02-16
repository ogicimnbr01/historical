"""Quick test script for dynamic topic generator."""
import sys
sys.path.insert(0, r'c:\tokmak\broje\shorts\historical\lambda\video_creator')

from dynamic_topic_generator import generate_dynamic_topic

# Test with empty blacklist
result = generate_dynamic_topic(
    past_entities=[],
    region_name='us-east-1'
)

print("\n🎯 Generated Topic:")
print(f"Title: {result.get('title') if result else 'FAILED'}")
if result:
    print(f"Wiki Entity: {result.get('wiki_entity')}")
    print(f"Era: {result.get('era')}")
    print(f"Category: {result.get('category')}")
    print(f"Obscurity Score: {result.get('obscurity_score')}/10")
else:
    print("❌ Topic generation failed")
