from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote

class Hysteria2Validator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        # Hysteria2 can start with 'hy2://' or 'hysteria2://'
        if not (link.startswith("hysteria2://") or link.startswith("hy2://")):
            return False
        try:
            # Normalize to 'hysteria2://' for consistent parsing
            normalized_link = link.replace("hy2://", "hysteria2://", 1)
            parsed_url = urlparse(normalized_link)
            
            password_part = parsed_url.username # Hysteria2 uses username as password
            if not password_part: return False

            host_port_part = parsed_url.netloc.split('@')[-1]
            if ':' not in host_port_part: return False

            host, port_str = host_port_part.rsplit(':', 1)
            port = int(port_str)

            if not BaseValidator._is_valid_port(port): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            query_params = parse_qs(parsed_url.query)
            # Hysteria2 always uses TLS, usually requires 'sni' or 'insecure=1' for self-signed
            if not ('sni' in query_params or ('insecure' in query_params and query_params['insecure'][0].lower() == '1')):
                return False # Stronger check than Hysteria v1
            
            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        cleaned_link = link.strip()
        # Normalize to 'hysteria2://' prefix
        if cleaned_link.startswith("hy2://"):
            cleaned_link = cleaned_link.replace("hy2://", "hysteria2://", 1)
        
        parts = cleaned_link.split('#', 1)
        if len(parts) > 1:
            main_part = parts[0]
            tag_part = unquote(parts[1])
            from urllib.parse import quote
            cleaned_link = f"{main_part}#{quote(tag_part.strip().replace(' ', '_'))}"
        return cleaned_link