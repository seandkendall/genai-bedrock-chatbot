import random, string, json

def process_message_history(existing_history):
    normalized_history = []
    for message in existing_history:
        # Extract role and content
        role = message.get('role')
        content = message.get('content')

        # Ensure role is present and valid
        if not role or role not in ['user', 'assistant']:
            continue  # Skip messages with invalid or missing roles

        # Normalize content format
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        elif isinstance(content, list):
            # Ensure each item in the list is correctly formatted
            content = [{'type': 'text', 'text': item['text']} if isinstance(item, dict) and 'text' in item else {'type': 'text', 'text': str(item)} for item in content]
        else:
            content = [{'type': 'text', 'text': str(content)}]

        # Create normalized message
        normalized_message = {'role': role, 'content': content}

        normalized_history.append(normalized_message)

    return normalized_history

def process_message_history_mistral_large(existing_history):
    normalized_history = []

    for message in existing_history:
        role = message.get('role')
        content = message.get('content')

        if role in ['user', 'assistant']:
            # Ensure content is a string
            content = str(content) if content is not None else ''
            
            # Create normalized message
            normalized_message = {
                'role': role,
                'content': content
            }
            
            normalized_history.append(normalized_message)

    return normalized_history

def generate_random_string(length=8):
    characters = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(characters) for _ in range(length))
    return f"RES{random_part}"

def replace_user_bot(text):
    return text.replace('User:', 'User;').replace('Bot:', 'Bot;')

def split_message(message, max_chunk_size=30 * 1024):  # 30 KB chunk size
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