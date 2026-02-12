import boto3
import json

secret_name = "shorts/youtube-oauth"
region_name = "us-east-1"
new_refresh_token = "PLACEHOLDER_TOKEN_REMOVED_FOR_SECURITY"

session = boto3.session.Session()
client = session.client(service_name='secretsmanager', region_name=region_name)

try:
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    secret_string = get_secret_value_response['SecretString']
    secret_dict = json.loads(secret_string)
    
    print("Old token ends with:", secret_dict.get('refresh_token', 'NOT_FOUND')[-10:])
    
    secret_dict['refresh_token'] = new_refresh_token
    
    client.put_secret_value(
        SecretId=secret_name,
        SecretString=json.dumps(secret_dict)
    )
    print("Secret updated successfully.")
    print("New token ends with:", new_refresh_token[-10:])
    
except Exception as e:
    print(f"Error updating secret: {e}")
