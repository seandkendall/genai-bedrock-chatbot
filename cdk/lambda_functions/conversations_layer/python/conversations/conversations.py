import json
from datetime import datetime, timezone, timedelta

def delete_conversation_history(dynamodb,conversations_table_name,logger,session_id):
    """Function to delete conversation history from DDB"""
    try:
        dynamodb.delete_item(
            TableName=conversations_table_name,
            Key={'session_id': {'S': session_id}}
        )
        logger.info(f"Conversation history deleted for session ID: {session_id}")
    except Exception as e:
        logger.exception(e)
        logger.error(f"Error deleting conversation history (9781): {str(e)}")
        
def query_existing_history(dynamodb,conversations_table_name,logger,session_id):
    """Function to query existing history from DDB"""
    try:
        response = dynamodb.get_item(
            TableName=conversations_table_name,
            Key={'session_id': {'S': session_id}},
            ProjectionExpression='title,conversation_history'
        )
        if 'Item' in response:
            conversation_history_string = response['Item']['conversation_history']['S']
            title_string = response['Item']['title']['S']
            needs_load_from_s3 = 's3source' in conversation_history_string
            return needs_load_from_s3,title_string,json.loads(conversation_history_string)

        return False,'',[]

    except Exception as e:
        logger.exception(e)
        logger.error("Error querying existing history: " + str(e))
        return False,'',[]        
    
def load_and_send_conversation_history(session_id:str, connection_id:str, user_id:str, dynamodb,conversations_table_name,s3_client,conversation_history_bucket,logger, commons,apigateway_management_api):
    """Function to load and send conversation history"""
    try:
        response = dynamodb.get_item(
            TableName=conversations_table_name,
            Key={'session_id': {'S': session_id}}
        )

        if 'Item' in response:
            item = response['Item']
            conversation_history_in_s3 = False
            conversation_history_in_s3_value = item.get('conversation_history_in_s3', False)
            if isinstance(conversation_history_in_s3_value, dict):
                conversation_history_in_s3 = conversation_history_in_s3_value.get('BOOL', False)
            if conversation_history_in_s3:
                prefix = rf'{user_id}/{session_id}'
                # Load conversation history from S3
                response = s3_client.get_object(Bucket=conversation_history_bucket, Key=f"{prefix}/{session_id}.json")
                conversation_history = json.loads(response['Body'].read().decode('utf-8'))
            else:
                # Load conversation history from DynamoDB
                conversation_history_str = item['conversation_history']['S']
                conversation_history = json.loads(conversation_history_str)
            # Split the conversation history into chunks
            conversation_history_chunks = split_message(conversation_history)
            # Send the conversation history chunks to the WebSocket client
            total_chunks = len(conversation_history_chunks)
            for index, chunk in enumerate(conversation_history_chunks, start=1):
                commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'conversation_history',
                    'last_message': index == total_chunks,
                    'chunk': chunk,
                    'current_chunk': index,
                    'total_chunks': total_chunks
                })
        else:
            commons.send_websocket_message(logger, apigateway_management_api, connection_id, {
                    'type': 'no_conversation_to_load',
                    'last_message': True
                })
            return []

    except Exception as e:
        logger.error("Error loading conversation history")
        logger.exception(e)
        return []    

def split_message(message, max_chunk_size=30 * 1024):  # 30 KB chunk size
    """Function to split messages into 30Kb chunks to support websockets"""
    chunks = []
    current_chunk = []
    current_chunk_size = 0

    for msg in message:
        msg_json = json.dumps({'role': msg['role'], 'content': msg['content'], 'timestamp': msg['timestamp'], 'message_id': msg['message_id']})
        msg_size = len(msg_json.encode('utf-8'))

        if current_chunk_size + msg_size > max_chunk_size:
            chunks.append(json.dumps(current_chunk))
            current_chunk = []
            current_chunk_size = 0

        current_chunk.append(msg)
        current_chunk_size += msg_size

    if current_chunk:
        chunks.append(json.dumps(current_chunk))

    return chunks

def save_token_usage(user_id, input_tokens,output_tokens,dynamodb,usage_table_name):
    """Function to save token usage in DDB"""
    current_date_ymd = datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')
    current_date_ym = datetime.now(tz=timezone.utc).strftime('%Y-%m')
    
    dynamodb.update_item(
                    TableName=usage_table_name,
                    Key={'user_id': {'S': user_id }},
                    UpdateExpression=f"ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
                    ExpressionAttributeValues={
                        ':input_tokens': {'N': str(input_tokens)},
                        ':output_tokens': {'N': str(output_tokens)},
                        ':message_count': {'N': str(1)}
                    }
                )
    dynamodb.update_item(
                    TableName=usage_table_name,
                    Key={'user_id': {'S': user_id + '-' + current_date_ym}},
                    UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
                    ExpressionAttributeValues={
                        ':input_tokens': {'N': str(input_tokens)},
                        ':output_tokens': {'N': str(output_tokens)},
                        ':message_count': {'N': str(1)}
                    }
                )
    dynamodb.update_item(
                    TableName=usage_table_name,
                    Key={'user_id': {'S': user_id + '-' + current_date_ymd}},
                    UpdateExpression="ADD input_tokens :input_tokens, output_tokens :output_tokens, message_count :message_count",
                    ExpressionAttributeValues={
                        ':input_tokens': {'N': str(input_tokens)},
                        ':output_tokens': {'N': str(output_tokens)},
                        ':message_count': {'N': str(1)}
                    }
                ) 