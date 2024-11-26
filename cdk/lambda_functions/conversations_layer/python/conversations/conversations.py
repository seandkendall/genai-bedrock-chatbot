import json

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
        print('SDK: SDK887: Do we need to load a conversation from s3 instead of DDB?')
        print(response)
        print('SDK: END SDK887 ')
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