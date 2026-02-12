import boto3
import json
from decimal import Decimal

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('shorts_video_metrics')

try:
    response = table.scan(
        FilterExpression="#st = :s",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":s": "linked"}
    )
    items = response.get('Items', [])
    print(f"Found {len(items)} linked videos.")
    if items:
        print(json.dumps(items[0], indent=2, default=decimal_default))
        
    # Also check for 'complete' status as weekly_report looks for 'complete'
    response_complete = table.scan(
        FilterExpression="#st = :s",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":s": "complete"}
    )
    items_complete = response_complete.get('Items', [])
    print(f"Found {len(items_complete)} complete videos.")

except Exception as e:
    print(str(e))
