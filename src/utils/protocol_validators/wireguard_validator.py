import base64
from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class WireguardValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("wireguard://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            query_params = parse_qs(parsed_url.query)

            # WireGuard links MUST contain a 'publickey' parameter
            if 'publickey' not in query_params or not query_params['publickey'][0]:
                return False
            
            # Endpoint is usually host:port
            if 'endpoint' in query_params and query_params['endpoint'][0]:
                endpoint = query_params['endpoint'][0]
                if ':' not in endpoint: return False
                host, port_str = endpoint.rsplit(':', 1)
                if not BaseValidator._is_valid_port(int(port_str)): return False
                if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                    return False
            
            # The 'netloc' part might contain a key as well, but 'publickey' in query is more standard for links.
            # No strict validation for 'privatekey' if it's there (often not in shareable links).
            
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