import sys
import os
import json
import logging

# Add lambda directory to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

# Mock environment variables
os.environ['AWS_REGION_NAME'] = 'us-east-1'
os.environ['METRICS_TABLE_NAME'] = 'shorts_video_metrics'
os.environ['JOBS_TABLE_NAME'] = 'shorts_jobs'
os.environ['RUN_LOGS_TABLE_NAME'] = 'shorts_run_logs'
os.environ['S3_BUCKET_NAME'] = 'test-bucket'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'

# Import handler
from handler import lambda_handler

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_viking_trigger():
    print("Testing Viking Trigger...")
    
    event = {
        "topic": "The day Vikings attacked Paris",
        "category": "medieval", # Force category for test
        "job_id": "test-viking-job-001",
        "force_mode": "QUALITY" # Ensure pipeline is used
    }
    
    try:
        # Mocking boto3 to avoid actual AWS calls during simple logic verification
        # But wait, the user wants me to actually run it... 
        # If I run it locally, I need AWS credentials. 
        # The user has AWS credentials configured on their machine.
        # However, running the FULL generation (Image, Voice, Music) might take too long or cost money.
        # But the request says "Manually set next video topic... Verify changes."
        # This implies running it.
        
        # Let's run it!
        result = lambda_handler(event, None)
        print("\n✅ Verification Result:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_viking_trigger()
