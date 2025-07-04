import base64
import re
from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote, quote

class SsrValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("ssr://"):
            return False
        try:
            base64_part_with_tag = link[6:]
            base64_part = base64_part_with_tag.split('#')[0].split('/?')[0] # Remove tag and query for decoding

            # Add padding and decode
            base64_part_padded = base64_part.replace('-', '+').replace('_', '/')
            missing_padding = len(base64_part_padded) % 4
            if missing_padding != 0:
                base64_part_padded += '=' * (4 - missing_padding)
            
            decoded_bytes = base64.b64decode(base64_part_padded, validate=True)
            decoded_str = decoded_bytes.decode('utf-8')

            # Expected format after decoding: server:port:protocol:method:obfs:password_base64/?params#tag
            parts = decoded_str.split(':')
            if len(parts) < 6: # server, port, protocol, method, obfs, password
                return False

            host = parts[0]
            port = int(parts[1])
            protocol = parts[2] # SSR Protocol
            method = parts[3]
            obfs = parts[4]
            password_encoded = parts[5].split('/?')[0] # Get password part before query string

            if not BaseValidator._is_valid_port(port):
                return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # Password part can be empty, but if present, should be decodable (urlsafe base64)
            if password_encoded:
                try:
                    base64.urlsafe_b64decode(password_encoded + '==').decode('utf-8')
                except Exception:
                    return False # Invalid password base64

            # Query parameters are often base64 encoded for SSR (e.g. obfsparam, protparam)
            # Full validation of these is complex but basic structure should be fine.

            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        cleaned_link = link.strip()
        
        # Extract base64 part and tag
        base64_part_with_tag = cleaned_link[6:]
        main_part_components = base64_part_with_tag.split('#', 1)
        base64_core = main_part_components[0]
        tag = ""
        if len(main_part_components) > 1:
            tag = unquote(main_part_components[1])
            tag = tag.strip().replace(' ', '_')
            tag = quote(tag)

        # Re-encode the main base64 part to ensure proper padding and valid characters
        # This is crucial for SSR as the entire config is base64
        try:
            # Add padding, decode, then re-encode for a clean version
            base64_part_padded = base64_core.replace('-', '+').replace('_', '/')
            missing_padding = len(base64_part_padded) % 4
            if missing_padding != 0:
                base64_part_padded += '=' * (4 - missing_padding)
            
            decoded_str = base64.b64decode(base64_part_padded, validate=True).decode('utf-8')
            re_encoded_b64 = base64.urlsafe_b64encode(decoded_str.encode('utf-8')).decode().rstrip('=')
            main_part = f"ssr://{re_encoded_b64}"

        except Exception:
            # If it's not valid base64 (should be caught by is_valid), return original or simplified
            main_part = f"ssr://{base64_core}" # Fallback to original encoded part if re-encoding fails
        
        if tag:
            return f"{main_part}#{tag}"
        return main_part