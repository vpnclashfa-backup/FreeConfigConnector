import base64
import re
from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, unquote, quote

class SsValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("ss://"):
            return False
        try:
            base_part_with_tag = link[5:]
            base_part = base_part_with_tag.split('#')[0] # ignore tag for core validation
            
            # Check if it's base64 encoded
            try:
                # Attempt to decode assuming it's the full base64 string
                decoded_str_bytes = base64.urlsafe_b64decode(base_part + '==')
                decoded_str = decoded_str_bytes.decode('utf-8')
                
                # If successfully decoded, expect format method:password@server:port
                if '@' not in decoded_str or ':' not in decoded_str.split('@')[-1]:
                    return False # Invalid decoded format

                user_info, server_info = decoded_str.rsplit('@', 1)
                method, password = user_info.split(':', 1)
                host, port_str = server_info.rsplit(':', 1)

            except Exception:
                # Not base64 encoded, assume direct method:password@server:port
                if '@' not in base_part or ':' not in base_part.split('@')[-1]:
                    return False

                user_info, server_info = base_part.rsplit('@', 1)
                if ':' not in user_info: # Method:Password
                    return False

                method, password = user_info.split(':', 1)
                host, port_str = server_info.rsplit(':', 1)

            port = int(port_str)

            if not BaseValidator._is_valid_port(port):
                return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False

            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        cleaned_link = link.strip()
        
        # Extract base part and tag
        parts = cleaned_link.split('#', 1)
        main_part = parts[0]
        tag = ""
        if len(parts) > 1:
            tag = unquote(parts[1]) # Decode tag first
            tag = tag.strip().replace(' ', '_') # Clean tag (e.g., spaces to underscores)
            tag = quote(tag) # Re-encode for URL safety

        # Reconstruct base64 part for consistency if it's encoded
        if main_part.startswith("ss://"):
            core_link_part = main_part[5:]
            if '@' in core_link_part:
                auth_part, addr_part = core_link_part.split('@', 1)
                try:
                    # If auth_part is base64, ensure it's properly re-encoded
                    decoded_auth = base64.urlsafe_b64decode(auth_part + '==').decode('utf-8')
                    re_encoded_auth = base64.urlsafe_b64encode(decoded_auth.encode('utf-8')).decode().rstrip('=')
                    main_part = f"ss://{re_encoded_auth}@{addr_part}"
                except Exception:
                    # If not base64, leave as is (method:password format)
                    pass
            
        if tag:
            return f"{main_part}#{tag}"
        return main_part