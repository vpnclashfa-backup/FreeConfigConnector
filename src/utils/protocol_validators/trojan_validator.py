from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote

class TrojanValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("trojan://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            password_part = parsed_url.username # Password is the username part
            if not password_part: return False # Trojan needs a password

            host_port_part = parsed_url.netloc.split('@')[-1] # host:port, can be with or without password@
            if ':' not in host_port_part: return False
            
            host, port_str = host_port_part.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # Query parameters (e.g., sni, alpn, flow)
            query_params = parse_qs(parsed_url.query)
            
            # Basic check for TLS parameters if any
            if 'security' in query_params and query_params['security'][0] != 'tls':
                return False # Trojan usually implies TLS

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
            from urllib.parse import quote
            cleaned_link = f"{main_part}#{quote(tag_part.strip().replace(' ', '_'))}"
        return cleaned_link