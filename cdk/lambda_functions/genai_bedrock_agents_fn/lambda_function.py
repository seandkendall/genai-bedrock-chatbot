import json
import datetime
import random
import boto3
import os
import logging
from botocore.exceptions import ClientError
from aws_lambda_powertools import Tracer


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
dynamodb = boto3.resource('dynamodb')
tracer = Tracer()

try:
    dynamodb_table_name = os.environ['DYNAMODB_TABLE']
except KeyError:
    logger.error("DYNAMODB_TABLE environment variable is not set")
    raise

incidents_table = dynamodb.Table(dynamodb_table_name)

@tracer.capture_lambda_handler
def lambda_handler(event, context):

    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    http_method = event.get('httpMethod', '')
    session_attributes = event.get('sessionAttributes', {})
    prompt_session_attributes = event.get('promptSessionAttributes', {})
    request_body = event.get('requestBody', {}).get('content', {}).get('application/json', {})

    if api_path == '/newincident' and http_method == 'POST':
        try:
            incident_data = {
                prop['name']: prop['value']
                for prop in request_body.get('properties', [])
            }
            # logger.debug(f'Incident data: {incident_data}')
            validate_incident_data(incident_data)
            return create_incident(action_group, incident_data, session_attributes, prompt_session_attributes, api_path, http_method)
        except (ValueError, KeyError) as e:
            logger.exception(e)
            return error_response(action_group, api_path, http_method, 400, str(e), session_attributes, prompt_session_attributes)

    elif api_path.startswith('/getincident/') and http_method == 'GET':
        return get_incident(action_group, session_attributes, prompt_session_attributes, event, api_path, http_method)

    else:
        return error_response(action_group, api_path, http_method, 404, 'Not Found', session_attributes, prompt_session_attributes)

@tracer.capture_method
def validate_incident_data(incident_data):
    required_fields = ['firstName', 'lastName', 'location', 'description']
    missing_fields = [field for field in required_fields if field not in incident_data]
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    severity = incident_data.get('severity', 0)
    try:
        severity = int(severity)
    except ValueError:
        raise ValueError("Severity must be an integer value")

    if severity < 1 or severity > 5:
        raise ValueError(f"Severity must be between 1 and 5, but received {severity}")

    for field in ['firstName', 'lastName', 'location', 'description']:
        if not incident_data[field].strip():
            raise ValueError(f"{field} cannot be an empty string")

@tracer.capture_method
def create_incident(action_group, incident_data, session_attributes, prompt_session_attributes, api_path, http_method):
    now = datetime.datetime.now()
    incident_id_prefix = f"INC{now.year}{now.month:02d}{now.day:02d}{now.hour:02d}{now.minute:02d}{now.second:02d}"
    incident_id_suffix = f"{random.randint(1000, 9999)}"
    incident_id = f"{incident_id_prefix}{incident_id_suffix}"

    incident = {
        'incident_id': incident_id,
        'status': 'open',
        **incident_data  # Merge additional incident data
    }
    # logger.debug(f'Creating incident: {incident}')

    try:
        incidents_table.put_item(Item=incident)
    except ClientError as e:
        logger.exception(f"Error creating incident: {e}")
        return error_response(action_group, api_path, http_method, 500, 'Error creating incident', session_attributes, prompt_session_attributes)

    response_body = {
        'application/json': {
            'body': json.dumps({'incident_id': incident_id, **incident_data})
        }
    }
    # logger.debug(f'Response body: {response_body}')

    return success_response(action_group, api_path, http_method, 201, response_body, session_attributes, prompt_session_attributes)

@tracer.capture_method
def get_incident(action_group, session_attributes, prompt_session_attributes, event, api_path, http_method):
    incident_id = None
    for param in event.get('parameters', []):
        if param['name'] == 'incident_id':
            incident_id = param['value']
            break

    if not incident_id:
        return error_response(action_group, api_path, http_method, 400, 'Missing incident_id parameter', session_attributes, prompt_session_attributes)

    try:
        response = incidents_table.get_item(Key={'incident_id': incident_id})
    except ClientError as e:
        logger.exception(f"Error getting incident: {e}")
        return error_response(action_group, api_path, http_method, 500, 'Error getting incident', session_attributes, prompt_session_attributes)

    if 'Item' in response:
        incident = response['Item']
        # logger.debug(f'Retrieved incident: {incident}')
        response_body = {
            'application/json': {
                'body': json.dumps(incident)
            }
        }
        return success_response(action_group, api_path, http_method, 200, response_body, session_attributes, prompt_session_attributes)
    else:
        logger.debug(f'Incident {incident_id} not found')
        return error_response(action_group, api_path, http_method, 404, f'Incident {incident_id} not found', session_attributes, prompt_session_attributes)

@tracer.capture_method
def success_response(action_group, api_path, http_method, status_code, response_body, session_attributes, prompt_session_attributes):
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': status_code,
            'responseBody': response_body
        },
        'sessionAttributes': session_attributes,
        'promptSessionAttributes': prompt_session_attributes
    }

@tracer.capture_method
def error_response(action_group, api_path, http_method, status_code, error_message, session_attributes, prompt_session_attributes):
    response_body = {
        'application/json': {
            'body': json.dumps({'error': error_message})
        }
    }
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': status_code,
            'responseBody': response_body
        },
        'sessionAttributes': session_attributes,
        'promptSessionAttributes': prompt_session_attributes
    }
