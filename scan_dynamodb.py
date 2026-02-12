import boto3
import json

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('shorts_video_metrics')

response = table.scan()
items = response.get('Items', [])

print(f"Total items: {len(items)}")

for item in items:
    vid = item.get('video_id')
    status = item.get('status')
    eligible = item.get('calibration_eligible')
    fetched_at = item.get('analytics_fetched_at_utc')
    
    print(f"ID: {vid} | Status: {status} | Eligible: {eligible} | Fetched: {fetched_at}")
