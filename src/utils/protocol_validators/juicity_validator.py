from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote

class JuicityValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("juicity://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            user_pass_part = parsed_url.username # Juicity uses username for password/uuid
            if not user_pass_part: return False # Need a credential part

            host_port_part = parsed_url.netloc.split('@')[-1]
            if ':' not in host_port_part: return False

            host, port_str = host_port_part.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            query_params = parse_qs(parsed_url.query)
            # Juicity often uses 'security=tls', and 'sni' or 'insecure=1'
            if not ('security' in query_params and query_params['security'][0] == 'tls'):
                return False # Juicity always uses TLS

            if not ('sni' in query_params or ('insecure' in query_params and query_params['insecure'][0].lower() == '1')):
                return False # Requires SNI or insecure flag
            
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