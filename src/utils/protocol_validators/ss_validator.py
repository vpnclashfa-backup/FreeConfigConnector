import base64
from src.utils.protocol_validators.base_validator import BaseValidator
from urllib.parse import urlparse, unquote

class SsValidator(BaseValidator):
    @staticmethod
    def is_valid(link: str) -> bool:
        if not link.startswith("ss://"):
            return False
        try:
            # SS links are usually ss://base64encoded_method_password@server:port#tag
            # Or sometimes ss://method:password@server:port#tag (less common for actual clients)
            base_part = link[5:]
            
            # Split by @
            parts = base_part.split('@')
            if len(parts) < 2:
                return False # Expect at least method_pass_base64@host:port

            method_pass_encoded = parts[0]
            server_info_part = parts[1]

            # Try to decode method_pass_encoded
            try:
                method_pass_decoded_bytes = base64.urlsafe_b64decode(method_pass_encoded + '==') # Add padding for safety
                method_pass_decoded = method_pass_decoded_bytes.decode('utf-8')
                if ':' not in method_pass_decoded:
                    return False # Expect method:password
            except Exception:
                # If not base64, assume it's direct method:password
                if ':' not in method_pass_encoded:
                    return False

            # Parse server:port
            server_host_part = server_info_part.split('#')[0] # Remove potential tag

            if ':' not in server_host_part:
                return False
            
            host, port_str = server_host_part.rsplit(':', 1) # rsplit for IPv6
            
            if not BaseValidator._is_valid_port(int(port_str)):
                return False
            if not (BaseValidator._is_valid_domain(host) or BaseValidator._is_valid_ipv4(host) or BaseValidator._is_valid_ipv6(host)):
                return False

            return True
        except Exception:
            return False

    @staticmethod
    def clean(link: str) -> str:
        # SS links can have fragmented parts or trailing data.
        # This cleaning attempts to keep only the core ss://...#tag part.
        cleaned_link = link.strip()
        
        # Remove anything after the # if it's not URL-encoded
        # Or re-encode the fragment if it contains spaces after decoding.
        parts = cleaned_link.split('#', 1)
        if len(parts) > 1:
            main_part = parts[0]
            tag_part = unquote(parts[1]) # Decode tag to clean, then re-encode if needed
            cleaned_link = f"{main_part}#{tag_part.strip().replace(' ', '_')}" # Simple cleanup, avoid spaces

        # Re-apply full base64 encoding logic if the first part is known to be base64
        # This is typically handled by ConfigParser's reconstruction, but this is a fallback.
        if cleaned_link.startswith("ss://"):
            core_part = cleaned_link[5:].split('#')[0] # Get the part before #
            if '@' in core_part:
                method_pass_encoded = core_part.split('@')[0]
                # If it looks like base64, ensure it's properly formatted base64
                try:
                    decoded_mp = base64.urlsafe_b64decode(method_pass_encoded + '==').decode('utf-8')
                    if ':' in decoded_mp: # Check if it decodes to method:password
                        # Re-encode to ensure correct urlsafe padding and no junk
                        re_encoded_mp = base64.urlsafe_b64encode(decoded_mp.encode('utf-8')).decode().rstrip('=')
                        cleaned_link = cleaned_link.replace(method_pass_encoded, re_encoded_mp, 1)
                except Exception:
                    pass # Not base64, or malformed base64, leave as is for now

        return cleaned_link