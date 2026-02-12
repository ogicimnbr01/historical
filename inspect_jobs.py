
import boto3
import json
from datetime import datetime

def inspect_jobs():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    try:
        table = dynamodb.Table('shorts_jobs')
        response = table.scan()
        items = response.get('Items', [])
        
        # Sort by updated_at_utc desc
        items.sort(key=lambda x: x.get('updated_at_utc', ''), reverse=True)
        
        print(f"Found {len(items)} jobs.")
        for item in items[:5]:
            job_id = item.get('job_id')
            status = item.get('status')
            updated = item.get('updated_at_utc')
            title = item.get('title', 'N/A')
            error = item.get('error_message', '')
            
            print(f"[{updated}] {job_id} -> {status} | Title: {title}")
            if error:
                print(f"   ⚠️ Error: {error}")
                
    except Exception as e:
        print(f"Error scanning jobs table: {e}")

if __name__ == "__main__":
    inspect_jobs()
