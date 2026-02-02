import os
import json
import sys

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')

# Set environment
os.environ['S3_BUCKET_NAME'] = 'youtube-shorts-videos-20260119122010783300000001'
os.environ['PYTHONIOENCODING'] = 'utf-8'

from script_gen import generate_history_script

print('='*70)
print('FULL SCRIPT TEST - Complete Video Text')
print('='*70)

num_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 1

for i in range(num_tests):
    print(f'\n{"="*70}')
    print(f'VIDEO {i+1}')
    print('='*70)
    
    try:
        result = generate_history_script()
        
        print(f'\n📌 TITLE: {result.get("title", "N/A")}')
        print(f'🎭 MOOD: {result.get("mood", "N/A")} | ERA: {result.get("era", "N/A")}')
        print(f'🎵 MUSIC: {result.get("music_style", "N/A")}')
        print(f'📊 TOPIC: {result.get("original_topic", "N/A")}')
        
        print('\n' + '-'*70)
        print('📜 FULL VOICEOVER:')
        print('-'*70)
        voiceover = result.get('voiceover_text', '')
        print(voiceover)
        print(f'\n   Word count: {len(voiceover.split())} words')
        
        print('\n' + '-'*70)
        print('🎬 SEGMENTS:')
        print('-'*70)
        
        segments = result.get('segments', [])
        for j, seg in enumerate(segments):
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            text = seg.get('text', '')
            words = len(text.split())
            
            segment_type = ['HOOK', 'CONTEXT', 'FACT', 'FINAL'][min(j, 3)]
            print(f'\n  [{segment_type}] {start}s - {end}s ({words} words)')
            print(f'  TEXT: {text}')
            
            # Show image prompt (truncated)
            img_prompt = seg.get('image_prompt', '')[:100]
            if img_prompt:
                print(f'  IMAGE: {img_prompt}...')
        
        print('\n' + '-'*70)
        print('📊 QUALITY CHECK:')
        print('-'*70)
        
        hook = segments[0]['text'] if segments else ''
        final = segments[-1]['text'] if segments else ''
        hook_words = len(hook.split())
        final_words = len(final.split())
        
        # Hook quality
        if hook_words <= 8:
            print(f'  HOOK: ✅ EXCELLENT ({hook_words} words)')
        elif hook_words <= 12:
            print(f'  HOOK: ✅ GOOD ({hook_words} words)')
        else:
            print(f'  HOOK: ⚠️ TOO LONG ({hook_words} words)')
        
        # Final quality
        if final_words <= 10:
            print(f'  FINAL: ✅ PUNCHY ({final_words} words)')
        else:
            print(f'  FINAL: ⚠️ Could be shorter ({final_words} words)')
        
        # Total duration estimate
        total_words = len(voiceover.split())
        estimated_duration = total_words / 2.5  # ~2.5 words per second
        print(f'  DURATION: ~{estimated_duration:.1f}s (estimated)')
        
    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()

print('\n' + '='*70)
print('TEST COMPLETE')
print('='*70)
