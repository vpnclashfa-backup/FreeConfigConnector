from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class TuicValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("tuic://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            # TUIC can have user:pass@host:port or host:port with UUID/password in query
            user_pass_host_port_part = parsed_url.netloc
            
            host_port_only = user_pass_host_port_part
            if '@' in user_pass_host_port_part:
                user_pass_str, host_port_only = user_pass_host_port_part.split('@', 1)
                # If user:pass@, check user and pass format (can be UUID:password)
                if ':' not in user_pass_str:
                    return False # Expect ID:Password
                user_id, password = user_pass_str.split(':', 1)
                if not BaseValidator._is_valid_uuid(user_id): # TUIC often uses UUID as ID
                    pass # Being permissive, some might not use UUID
            
            if ':' not in host_port_only: return False

            host, port_str = host_port_only.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # TUIC requires specific query parameters like 'uuid', 'password' (for TUICv5 if not in userinfo)
            query_params = parse_qs(parsed_url.query)
            
            # If UUID/Password not in userinfo, they should be in query
            if '@' not in user_pass_host_port_part: # This is a TUICv5-like link (no user/pass in netloc)
                if not ('uuid' in query_params and 'password' in query_params):
                    return False 
            
            # Minimal check for 'insecure' or 'allow_insecure' (common for TUIC)
            # if 'allow_insecure' in query_params and query_params['allow_insecure'][0].lower() == '1':
            #     pass
            
            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        cleaned_link = link.strip()
        parts = cleaned_link.split('#', 1)
        if len(parts) > 1:
            main_part = parts[0]
            tag_part = unquote(parts[1])
            tag_part = tag_part.strip().replace(' ', '_')
            cleaned_link = f"{main_part}#{quote(tag_part)}"
        return cleaned_link