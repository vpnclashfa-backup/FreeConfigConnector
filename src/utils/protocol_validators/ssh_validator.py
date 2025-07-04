from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, unquote

class SshValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not (link.startswith("ssh://") or link.startswith("sftp://")):
            return False
        try:
            parsed_url = urlparse(link)
            
            user_host_port_part = parsed_url.netloc
            if '@' not in user_host_port_part:
                # Can be just host:port if username is implied or not used
                host_port = user_host_port_part
            else:
                user_part, host_port = user_host_port_part.split('@', 1)
                if not user_part: return False # User should not be empty if provided

            if ':' not in host_port:
                # Default SSH port 22 or assume no port
                host = host_port
                port = 22 # Default SSH port
            else:
                host, port_str = host_port.rsplit(':', 1)
                port = int(port_str)
                if not BaseValidator._is_valid_port(port): return False

            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # SSH links usually don't have complex query params like other VPNs, mostly password or key in URL
            # but that's less common for actual SSH clients in URL format.
            
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