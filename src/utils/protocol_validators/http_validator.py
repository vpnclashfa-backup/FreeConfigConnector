from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse

class HttpValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not (link.startswith("http://") or link.startswith("https://")):
            return False
        try:
            parsed_url = urlparse(link)
            # Basic validation: must have a scheme, network location (host:port), and a valid port.
            if not parsed_url.scheme or not parsed_url.netloc:
                return False
            
            host, port_str = (parsed_url.hostname or ""), (parsed_url.port or 80)
            if not BaseValidator._is_valid_port(port_str):
                return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        # HTTP links are generally clean, just strip whitespace
        return link.strip()