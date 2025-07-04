import base64
from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, parse_qs, unquote

class SsrValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("ssr://"):
            return False
        try:
            # SSR links are usually ssr://base64encoded_all_params
            base64_part = link[6:]
            
            # Add padding and decode
            base64_part_padded = base64_part.replace('-', '+').replace('_', '/')
            missing_padding = len(base64_part_padded) % 4
            if missing_padding != 0:
                base64_part_padded += '=' * (4 - missing_padding)
            
            decoded_bytes = base64.b64decode(base64_part_padded, validate=True)
            decoded_str = decoded_bytes.decode('utf-8')

            # Expected format: server:port:protocol:method:obfs:password_base64/?params#tag
            parts = decoded_str.split(':')
            if len(parts) < 6:
                return False # Minimum required parts

            # Basic checks on core components
            host = parts[0]
            port = int(parts[1])
            protocol = parts[2]
            method = parts[3]
            obfs = parts[4]
            password_base64 = parts[5].split('/?')[0] # password part, before query or tag

            if not BaseValidator._is_valid_port(port):
                return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False
            
            # Password part can be empty, but if present, should be decodable
            if password_base64:
                try:
                    base64.urlsafe_b64decode(password_base64 + '==').decode('utf-8')
                except Exception:
                    return False # Invalid password base64

            # Protocol and OBFS parameters can be base64-encoded or plain.
            # More rigorous checks can be added here if needed for specific protocols/obfs types.

            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        # SSR links are entirely base64 encoded, so main cleaning is just stripping whitespace
        # Any internal junk should make is_valid return False.
        cleaned_link = link.strip()
        
        # If there's a tag, ensure it's URL-encoded for consistency
        parts = cleaned_link.split('#', 1)
        if len(parts) > 1:
            main_part = parts[0]
            tag_part = unquote(parts[1])
            # Re-encode tag after cleaning
            from urllib.parse import quote
            cleaned_link = f"{main_part}#{quote(tag_part.strip().replace(' ', '_'))}"

        # Re-encode the main base64 part to ensure proper padding and valid characters
        if cleaned_link.startswith("ssr://"):
            base64_part = cleaned_link[6:].split('#')[0]
            try:
                # Add padding, decode, then re-encode for a clean version
                base64_part_padded = base64_part.replace('-', '+').replace('_', '/')
                missing_padding = len(base64_part_padded) % 4
                if missing_padding != 0:
                    base64_part_padded += '=' * (4 - missing_padding)
                
                decoded_str = base64.b64decode(base64_part_padded, validate=True).decode('utf-8')
                re_encoded_b64 = base64.urlsafe_b64encode(decoded_str.encode('utf-8')).decode().rstrip('=')
                cleaned_link = cleaned_link.replace(base64_part, re_encoded_b64, 1) # Replace only first occurrence

            except Exception:
                pass # If it's not valid base64, leave as is (should be caught by is_valid)
        
        return cleaned_link