
import boto3
import json
import uuid
import sys

def trigger_aztec_video():
    """
    Manually trigger the video generator lambda for 'The Aztec Death Whistle'
    Uses the new Visual Director + Anthropology Category
    """
    
    # Configuration
    FUNCTION_NAME = "youtube-shorts-video-generator"
    TOPIC = "The terrifying sound of the Aztec Death Whistle"
    ERA = "ancient"
    CATEGORY = "anthropology_and_culture"
    
    payload = {
        "job_id": f"manual_trigger_{uuid.uuid4().hex[:8]}",
        "topic": TOPIC,
        "era": ERA,
        "category": CATEGORY,
        "mark_as_test": True,
        "force_mode": "QUALITY"
    }
    
    print(f"🚀 Triggering Lambda: {FUNCTION_NAME}")
    print(f"📜 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        lambda_client = boto3.client('lambda', region_name='us-east-1')
        
        # Invoke asynchronously (Event) or RequestResponse (Wait)
        # We use RequestResponse to see the logs immediately
        response = lambda_client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        status = response['StatusCode']
        response_payload = json.loads(response['Payload'].read())
        
        if status == 200:
            print("\n✅ Success! Lambda executed.")
            print(f"🎬 Video Title: {response_payload.get('body', {}).get('title', 'Unknown')}")
            # Parse body (it comes as string in API Gateway proxy format usually, but here likely direct)
            # Actually handler returns dict with body as string
            
            try:
                # Handle API Gateway style response
                body_json = json.loads(response_payload.get('body', '{}'))
                print(f"🔗 Download: {body_json.get('download_url')}")
                print(f"📄 License Report: {body_json.get('license_report')}")
            except:
                print(f"📦 Raw Response: {response_payload}")
                
        else:
            print(f"\n❌ Error: Status {status}")
            print(response_payload)
            
    except Exception as e:
        print(f"\n❌ Failed to invoke lambda: {e}")

if __name__ == "__main__":
    trigger_aztec_video()
