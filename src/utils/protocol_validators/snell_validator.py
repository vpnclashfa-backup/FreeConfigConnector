from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class SnellValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("snell://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            # Snell links use clientid@server:port format, or just server:port
            netloc_parts = parsed_url.netloc.split('@')
            host_port_part = netloc_parts[-1] # Always the last part after @

            if ':' not in host_port_part: return False
            
            host, port_str = host_port_part.rsplit(':', 1)
            
            if not BaseValidator._is_valid_port(int(port_str)): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # Snell often has 'psk' (Pre-Shared Key) in query params.
            query_params = parse_qs(parsed_url.query)
            if not 'psk' in query_params or not query_params['psk'][0]:
                return False # PSK is usually required for Snell

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