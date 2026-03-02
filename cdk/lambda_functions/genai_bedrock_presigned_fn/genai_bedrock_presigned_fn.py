import json
import boto3
import random
import re
import string
import os
from aws_lambda_powertools import Logger, Tracer

logger = Logger(service="S3PreSignedURL")
tracer = Tracer()

s3_client = boto3.client('s3')
attachment_bucket_name = os.environ['ATTACHMENT_BUCKET_NAME']
user_cache = {}
cognito_client = boto3.client('cognito-idp')

ALLOWED_MIME_TYPES = [
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'video/mp4', 'video/webm', 'video/3gp',
    'application/pdf', 'text/plain', 'text/csv', 'text/html', 'text/markdown',
    'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
]


def sanitize_filename(filename):
    """Remove path separators and special characters from filename"""
    # Remove path separators and null bytes
    filename = filename.replace('/', '').replace('\\', '').replace('\x00', '')
    # Remove any directory traversal patterns
    filename = filename.replace('..', '')
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    # Ensure filename is not empty after sanitization
    if not filename.strip():
        filename = 'unnamed_file'
    return filename

@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda Hander Function"""
    try:
        # Parse the request body
        request_body = json.loads(event['body'])
        access_token = request_body.get('accessToken', 'none')
        session_id = request_body.get('session_id', 'XYZ')
        user_id = access_token['payload']['sub']
        file_name = sanitize_filename(request_body['fileName'])
        file_type = request_body['fileType']
        # Validate file type against allowed MIME types
        if file_type not in ALLOWED_MIME_TYPES:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'File type not allowed'})
            }
        # generate random 8 character alpha numeric value
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        prefix = rf'{user_id}/{session_id}'
        # Generate a pre-signed URL for uploading
        presigned_post = s3_client.generate_presigned_post(
            Bucket=attachment_bucket_name,
            Key=f"{prefix}/{random_string}-{file_name}",
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type}
            ],
            ExpiresIn=3600
        )

        return {
            'statusCode': 200,
            'body': json.dumps(presigned_post)
        }
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error generating pre-signed URL: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Error generating pre-signed URL'})
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