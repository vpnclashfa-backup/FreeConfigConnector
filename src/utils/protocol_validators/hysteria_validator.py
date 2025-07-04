from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class HysteriaValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("hysteria://"):
            return False
        try:
            parsed_url = urlparse(link)
            host_port_part = parsed_url.netloc
            if ':' not in host_port_part: return False

            host, port_str = host_port_part.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            query_params = parse_qs(parsed_url.query)
            
            # Hysteria typically requires TLS parameters (peer, ca, autocert, insecure)
            if not ( 'peer' in query_params or 'ca' in query_params or 'autocert' in query_params or 
                     ('insecure' in query_params and query_params['insecure'][0].lower() == '1') ):
                # This check can be made stricter based on common Hysteria configs.
                # For now, it's a basic check that *some* TLS related param exists.
                pass # Making it permissive as in example, for broader acceptance.
            
            # Common parameters like 'up' (upload bandwidth), 'down' (download bandwidth), 'obfs'
            # No strict validation for values unless specified.
            
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