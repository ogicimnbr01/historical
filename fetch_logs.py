import boto3
import json

log_group = '/aws/lambda/youtube-shorts-analytics-fetcher'
client = boto3.client('logs', region_name='us-east-1')

def get_latest_stream():
    response = client.describe_log_streams(
        logGroupName=log_group,
        orderBy='LastEventTime',
        descending=True,
        limit=1
    )
    return response['logStreams'][0]['logStreamName']

def fetch_logs():
    stream_name = get_latest_stream()
    print(f"Fetching logs from: {stream_name}")
    
    response = client.get_log_events(
        logGroupName=log_group,
        logStreamName=stream_name,
        limit=20
    )
    
    events = response['events']
    with open('logs_output.txt', 'w', encoding='utf-8') as f:
        for event in events:
            f.write(f"{event['timestamp']} - {event['message']}")

if __name__ == '__main__':
    fetch_logs()
