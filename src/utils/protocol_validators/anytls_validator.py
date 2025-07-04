from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class AnytlsValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("anytls://"):
            return False
        try:
            parsed_url = urlparse(link)
            
            # Anytls typically includes server:port in netloc
            if not parsed_url.netloc: return False
            
            host, port_str = (parsed_url.hostname or ""), (parsed_url.port or 0)
            if not BaseValidator._is_valid_port(port_str): return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # Anytls is a generic TLS tunnel, might have parameters for SNI, ALPN etc.
            # For simplicity, we just check for basic URL structure for now.
            # Stricter checks like:
            # if not 'sni' in parse_qs(parsed_url.query) or not parse_qs(parsed_url.query)['sni'][0]: return False
            
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