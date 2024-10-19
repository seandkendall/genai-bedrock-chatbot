import json
import boto3
import random
import string
import os
from aws_lambda_powertools import Logger, Tracer

logger = Logger(service="S3PreSignedURL")
tracer = Tracer()

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ['ATTACHMENT_BUCKET']
user_cache = {}
cognito_client = boto3.client('cognito-idp')

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    
    try:
        # Parse the request body
        request_body = json.loads(event['body'])
        access_token = request_body.get('accessToken', 'none')
        session_id = request_body.get('session_id', 'XYZ')
        user_id = access_token['payload']['sub']
        file_name = request_body['fileName']
        file_type = request_body['fileType']
        # generate random 8 character alpha numeric value
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        
        

        # Generate a pre-signed URL for uploading
        presigned_post = s3_client.generate_presigned_post(
            Bucket=BUCKET_NAME,
            Key=f"{user_id}/{session_id}/{random_string}-{file_name}",
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type}
            ],
            ExpiresIn=3600
        )

        return {
            'statusCode': 200,
            'body': json.dumps(presigned_post),
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True,
            }
        }
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error generating pre-signed URL: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Error generating pre-signed URL'}),
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True,
            }
        }
        
def get_user_attributes(access_token):
    """Gets user attributes from cognito"""
    if access_token in user_cache:
        return user_cache[access_token]
    else:
        response = cognito_client.get_user(AccessToken=access_token)
        user_attributes = response['UserAttributes']
        user_cache[access_token] = user_attributes
        return user_attributes            