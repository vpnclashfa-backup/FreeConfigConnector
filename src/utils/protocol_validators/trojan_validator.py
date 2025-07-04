from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class TrojanValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("trojan://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            password_part = parsed_url.username # Password is the username part
            if not password_part: return False # Trojan needs a password

            # netloc could be password@host:port or just host:port if password is in raw link but not parsed by urlparse
            host_port_part = parsed_url.netloc
            if '@' in host_port_part: # If password was explicitly in netloc
                host_port_part = host_port_part.split('@', 1)[-1] # Take the host:port part

            if ':' not in host_port_part: return False
            
            host, port_str = host_port_part.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # Query parameters (e.g., sni, alpn, flow)
            query_params = parse_qs(parsed_url.query)
            
            # Trojan usually implies TLS. Check for explicit 'security=tls' or 'security=reality'
            # If security param exists and is not tls/reality/none, it might be invalid depending on strictness.
            security = query_params.get('security', ['tls'])[0].lower() # Default to tls
            if security not in ['tls', 'reality', 'none', '']: # Allow empty for very basic links
                return False 
            
            # If security is tls or reality, usually SNI is expected or insecure=1
            if security in ['tls', 'reality'] and not (
                'sni' in query_params or 
                ('allowinsecure' in query_params and query_params['allowinsecure'][0].lower() == '1') or
                ('insecure' in query_params and query_params['insecure'][0].lower() == '1')
            ):
                 # This check can be made more strict, but for now, if security is TLS/Reality,
                 # we expect either SNI or an insecure flag.
                pass 

            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        cleaned_link = link.strip()
        # Clean up potential fragment/tag after #
        parts = cleaned_link.split('#', 1)
        if len(parts) > 1:
            main_part = parts[0]
            tag_part = unquote(parts[1])
            tag_part = tag_part.strip().replace(' ', '_')
            cleaned_link = f"{main_part}#{quote(tag_part)}" # Re-encode for URL safety
        return cleaned_link