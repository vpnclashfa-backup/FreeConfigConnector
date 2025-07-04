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
            port = int(port_str) # Ensure port is an integer

            if not BaseValidator._is_valid_port(port):
                return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            return True
        except ValueError: # Catch specific ValueError for int() conversion
            return False
        except Exception: # Catch any other unexpected errors during parsing
            return False

    @staticmethod
    def clean(link: str) -> str:
        # Socks5 links are generally clean, just strip whitespace
        return link.strip()