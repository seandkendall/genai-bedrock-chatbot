import json
import re

class LightweightTokenizer:
    def __init__(self, tokenizer_json_path, config_json_path):
        # Load and parse configuration files
        with open(tokenizer_json_path) as f:
            self.tokenizer_config = json.load(f)
        with open(config_json_path) as f:
            self.model_config = json.load(f)
        
        # Extract chat template and special tokens
        self.chat_template = self.model_config.get('chat_template', [])
        self.special_tokens = {
            token['content']: token['id'] 
            for token in self.tokenizer_config['added_tokens']
        }
        
        # Initialize base tokenization components
        self.vocab = self.tokenizer_config['model']['vocab']
        self.merges = self.tokenizer_config['model']['merges']
        self._build_merge_rules()

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        # Implement chat template formatting
        formatted = []
        system_prompt = next((m for m in messages if m['role'] == 'system'), None)
        
        # Add system prompt if present
        if system_prompt:
            formatted.append(f"{self.special_tokens['<|system|>']}{system_prompt['content']}")
        
        # Process conversation history
        for msg in messages:
            if msg['role'] == 'user':
                formatted.append(f"{self.special_tokens['<|user|>']}{msg['content']}")
            elif msg['role'] == 'assistant':
                formatted.append(f"{self.special_tokens['<|assistant|>']}{msg['content']}")
        
        # Add final response prompt if requested
        if add_generation_prompt:
            formatted.append(f"{self.special_tokens['<|assistant|>']}")
        
        # Join components and process
        joined_text = ''.join(formatted)
        return self.tokenize(joined_text) if tokenize else joined_text

    def _build_merge_rules(self):
        # Create merge priority dictionary
        self.merge_priority = {
            tuple(merge.split()): idx 
            for idx, merge in enumerate(self.merges)
        }

    def tokenize(self, text):
        # Implement BPE tokenization logic
        words = re.findall(r"\S+\n?", text)
        tokens = []
        
        for word in words:
            current_token = []
            for char in word:
                byte = f'<0x{ord(char):02X}>'
                current_token.append(byte)
                
                # Merge tokens using BPE rules
                while len(current_token) >= 2:
                    pair = (current_token[-2], current_token[-1])
                    if pair in self.merge_priority:
                        merged = f"{pair[0]}{pair[1]}"
                        current_token = current_token[:-2] + [merged]
                    else:
                        break
            
            tokens.extend(current_token)
        
        # Convert to token IDs
        return [
            self.vocab[token] if token in self.vocab else self.special_tokens['<|unk|>']
            for token in tokens
        ]