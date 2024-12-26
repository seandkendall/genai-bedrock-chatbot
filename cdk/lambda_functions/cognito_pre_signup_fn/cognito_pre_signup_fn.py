import os
import re

def lambda_handler(event, context):
    try:
        email = event['request']['userAttributes']['email']
        allowlist_domain = os.environ.get('ALLOWLIST_DOMAIN', '')
        
        if allowlist_domain:
            allowed_patterns = [pattern.strip() for pattern in allowlist_domain.split(',')]
            for pattern in allowed_patterns:
                if pattern.startswith('@'):
                    if email.endswith(pattern):
                        event['response']['autoConfirmUser'] = True
                        event['response']['autoVerifyEmail'] = True
                        return event
                elif pattern.endswith('.'):
                    if any(email.endswith(domain) for domain in [pattern, pattern[:-1]]):
                        event['response']['autoConfirmUser'] = True
                        event['response']['autoVerifyEmail'] = True
                        return event
                elif pattern in email:
                    event['response']['autoConfirmUser'] = True
                    event['response']['autoVerifyEmail'] = True
                    return event
            
            # If the email doesn't match any of the allowed patterns, reject the sign-up
            raise Exception("Email is not on the allowed list.")
        else:
            # If the ALLOWLIST_DOMAIN is empty, allow the sign-up as long as the email is valid
            if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                return event
            else:
                raise Exception("Invalid email address.")

    except (KeyError, ValueError):
        raise Exception("Invalid request format.")