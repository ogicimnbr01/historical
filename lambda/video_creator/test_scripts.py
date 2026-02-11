import os
import json
import sys

# Fix Windows encoding
sys.stdout.reconfigure(encoding='utf-8')  # pyre-ignore[16]

# Set environment
os.environ['S3_BUCKET_NAME'] = 'youtube-shorts-videos-20260119122010783300000001'
os.environ['PYTHONIOENCODING'] = 'utf-8'

from script_gen import generate_history_script  # pyre-ignore[21]

print('='*60)
print('SCRIPT TEST - Hook & Final Punch Quality Check')
print('='*60)

num_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 3

for i in range(num_tests):
    print(f'\n--- VIDEO {i+1} ---')
    try:
        result = generate_history_script()
        title = result.get('title', 'N/A')
        hook = result['segments'][0]['text'] if result.get('segments') else 'N/A'
        final = result['segments'][-1]['text'] if result.get('segments') else 'N/A'
        words = len(result.get('voiceover_text', '').split())
        hook_words = len(hook.split())
        final_words = len(final.split())
        
        print(f'TITLE: {title}')
        print(f'HOOK ({hook_words} words): {hook}')
        print(f'FINAL ({final_words} words): {final}')
        print(f'TOTAL: {words} words')
        
        # Quality check
        if hook_words <= 8:
            print('>>> HOOK: EXCELLENT')
        elif hook_words <= 12:
            print('>>> HOOK: GOOD')
        else:
            print('>>> HOOK: TOO LONG - needs work')
            
        if final_words <= 10:
            print('>>> FINAL: PUNCHY')
        else:
            print('>>> FINAL: Could be shorter')
            
    except Exception as e:
        print(f'ERROR: {e}')

print('\n' + '='*60)
print('TEST COMPLETE')
print('='*60)
