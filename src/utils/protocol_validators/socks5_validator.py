from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse

class Socks5Validator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("socks5://"):
            return False
        try:
            parsed_url = urlparse(link)
            if not parsed_url.netloc:
                return False
            
            # Socks5 can have user:pass@host:port or just host:port
            netloc_parts = parsed_url.netloc.split('@')
            host_port_part = netloc_parts[-1] # Always the last part after @

            if ':' not in host_port_part:
                return False
            
            host, port_str = host_port_part.rsplit(':', 1)
            
            if not BaseValidator._is_valid_port(int(port_str)):
                return False