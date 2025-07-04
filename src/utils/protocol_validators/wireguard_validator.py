from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote

class WireguardValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("wireguard://"):
            return False
        try:
            # Wireguard links are often in a format that's not a standard URL,
            # but rather wg://BASE64_CONFIG_OR_KEY?param=value#tag
            # A full WireGuard config validation would be complex (checking keys, addresses etc.)
            # For simplicity, we just check for base64 part and essential query params.

            parsed_url = urlparse(link)
            
            # The 'netloc' part might contain the key or be empty.
            # The actual config details are usually in query parameters or the base64 encoded part.
            
            # A WireGuard link MUST contain a 'publickey' parameter, and usually 'endpoint'.
            query_params = parse_qs(parsed_url.query)

            if not 'publickey' in query_params:
                return False
            
            # Endpoint is usually host:port
            if 'endpoint' in query_params:
                endpoint = query_params['endpoint'][0]
                if ':' not in endpoint: return False
                host, port_str = endpoint.rsplit(':', 1)
                if not BaseValidator._is_valid_port(int(port_str)): return False
                if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                    return False
            
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