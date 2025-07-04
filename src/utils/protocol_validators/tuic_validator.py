from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote

class TuicValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("tuic://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            user_pass_part = parsed_url.username # TUIC uses username as UUID or ID
            if not user_pass_part: return False # Need ID

            host_port_part = parsed_url.netloc.split('@')[-1]
            if ':' not in host_port_part: return False

            host, port_str = host_port_part.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # TUIC requires specific query parameters like 'uuid', 'password'
            query_params = parse_qs(parsed_url.query)
            
            if not ('uuid' in query_params and 'password' in query_params):
                # TUICv5 uses password in query params. TUICv4 uses username:password in userinfo
                # This validator assumes TUICv5 format with explicit uuid/password in query
                # If TUICv4 (user:pass@host:port) is needed, this logic needs adjustment.
                return False 
            
            # Minimal check for 'insecure' or 'allow_insecure'
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
            from urllib.parse import quote
            cleaned_link = f"{main_part}#{quote(tag_part.strip().replace(' ', '_'))}"
        return cleaned_link