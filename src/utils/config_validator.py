# src/utils/config_validator.py

import re
import base64
import json
from typing import Optional, Tuple, List
from urllib.parse import unquote, urlparse, parse_qs

# Import settings for active protocols if needed in validation logic
from src.utils.settings_manager import settings
from src.utils.protocol_definitions import PROTOCOL_REGEX_MAP # Import the base regex map

class ConfigValidator:
    @staticmethod
    def is_base64(s: str) -> bool:
        """Checks if a string is a valid base64 (or base64url) string."""
        try:
            s_clean = s.rstrip('=') # Remove padding for validation
            # Base64url alphabet uses - and _ instead of + and /
            return bool(re.match(r'^[A-Za-z0-9+/_-]*$', s_clean))
        except:
            return False

    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        """Decodes a base64url string (with - and _)."""
        try:
            s_padded = s.replace('-', '+').replace('_', '/') # Convert to standard base64 alphabet
            padding = 4 - (len(s_padded) % 4)
            if padding != 4: # Only add padding if necessary
                s_padded += '=' * padding
            return base64.b64decode(s_padded, validate=True)
        except:
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
        """Decodes a string that might be base64 encoded, returning UTF-8 text."""
        try:
            # Try to decode as standard base64 first
            decoded_bytes = base64.b64decode(text, validate=True)
            return decoded_bytes.decode('utf-8', errors='ignore')
        except:
            try:
                # If standard fails, try base64url
                decoded_bytes = ConfigValidator.decode_base64_url(text)
                if decoded_bytes:
                    return decoded_bytes.decode('utf-8', errors='ignore')
            except:
                pass
        return None

    @staticmethod
    def clean_vmess_config(config: str) -> str:
        """Cleans a Vmess link by stripping extra characters after base64 part."""
        if config.startswith("vmess://"):
            base64_part = config[8:]
            # Find the end of base64 part by looking for non-base64 chars or end of string
            clean_base64_part = re.match(r'[A-Za-z0-9+/=_-]*', base64_part)
            if clean_base64_part:
                return f"vmess://{clean_base64_part.group(0).strip()}"
        return config

    @staticmethod
    def normalize_hysteria2_protocol(config: str) -> str:
        """Normalizes 'hy2://' to 'hysteria2://'."""
        if config.startswith('hy2://'):
            return config.replace('hy2://', 'hysteria2://', 1)
        return config

    @staticmethod
    def is_vmess_config(config: str) -> bool:
        """Validates if a string is a structurally valid Vmess config."""
        try:
            if not config.startswith('vmess://'):
                return False
            base64_part = config[8:]
            decoded = ConfigValidator.decode_base64_text(base64_part) # Use general text decoder
            if decoded:
                json.loads(decoded) # Vmess payload is JSON
                return True
            return False
        except:
            return False

    @staticmethod
    def is_tuic_config(config: str) -> bool:
        """Validates if a string is a structurally valid TUIC config (basic check)."""
        try:
            if config.startswith('tuic://'):
                parsed = urlparse(config)
                # Basic check: should have a network location (host:port)
                return bool(parsed.netloc and ':' in parsed.netloc)
            return False
        except:
            return False
    
    @staticmethod
    def is_reality_config(config: str) -> bool:
        """
        Validates if a VLESS config includes valid Reality parameters.
        Reality needs: type=tcp (or other reality supported transports), security=reality, pbk, sni (and optionally fp).
        """
        try:
            if not config.startswith('vless://'):
                return False
            
            parsed = urlparse(config)
            query_params = parse_qs(parsed.query) # parse_qs returns dict of lists
            
            # Check for required Reality parameters
            security_val = query_params.get('security', [''])[0].lower()
            pbk_val = query_params.get('pbk', [''])[0]
            sni_val = query_params.get('sni', [''])[0]
            
            # Reality typically uses TCP transport, flow=xtls-rprx-vision etc.
            # A common type for Reality is tcp or ws
            type_val = query_params.get('type', [''])[0].lower() # default to empty string if not present
            
            # Basic check for host:port
            if not (parsed.netloc and ':' in parsed.netloc):
                return False

            # Minimal Reality validation: security=reality, pbk and sni must be present
            is_reality = (security_val == 'reality' and bool(pbk_val) and bool(sni_val))
            
            # Can add more checks here if needed, e.g., for specific 'type' or 'flow'
            # For robustness, we check only the essential Reality parameters.
            return is_reality
        except Exception:
            return False


    @staticmethod
    def is_valid_protocol_prefix(config_str: str) -> bool:
        """Checks if a string starts with a known protocol prefix from PROTOCOL_REGEX_MAP."""
        return any(config_str.startswith(p + '://') for p in PROTOCOL_REGEX_MAP.keys())


    @staticmethod
    def clean_config_string(config: str) -> str:
        """
        Removes common junk characters, emojis, and excessive whitespace from a config string.
        """
        # Remove common emojis and non-printable characters
        config = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\ufe00-\ufe0f\u200b-\u200d\uFEFF\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', config)
        # Remove numbers with circle Unicode variations (e.g., 1️⃣, 2️⃣)
        config = re.sub(r'\d{1,2}\ufe0f?', '', config)
        # Remove common Farsi/Arabic joining characters or repeated symbols (e.g., 🛜 ❓ ❗️ 🔤, etc. from the sample text)
        config = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u06F0-\u06F9\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFE00-\uFE0F\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\ufeff\u200d\s]*[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]+', '', config)
        config = re.sub(r'\s+', ' ', config) # Reduce multiple spaces to single space
        return config.strip()

    @staticmethod
    def split_configs_from_text(text: str, protocols_regex: re.Pattern) -> List[str]:
        """
        Extracts all potential config strings from a larger text, handling concatenations.
        Uses a combined regex to find all protocol starts and then extracts the content
        between starts. This is designed to be more robust against junk characters.
        """
        extracted_raw_configs: List[str] = []
        
        # Find all occurrences of known protocol prefixes
        matches = list(protocols_regex.finditer(text))
        
        if not matches:
            return []

        for i, match in enumerate(matches):
            start_index = match.start()
            end_index = -1

            if i + 1 < len(matches):
                # The end of current config is the start of the next one
                end_index = matches[i+1].start()
            else:
                # Last config, goes till the end of the text
                end_index = len(text)
            
            raw_config_candidate = text[start_index:end_index].strip()
            
            # Apply general cleaning first
            cleaned_candidate = ConfigValidator.clean_config_string(raw_config_candidate)
            
            # Apply protocol-specific cleaning based on its detected start
            # This is crucial for protocols like vmess/hy2 which have specific end patterns.
            if cleaned_candidate.startswith("vmess://"):
                cleaned_candidate = ConfigValidator.clean_vmess_config(cleaned_candidate)
            elif cleaned_candidate.startswith("hy2://"):
                cleaned_candidate = ConfigValidator.normalize_hysteria2_protocol(cleaned_candidate)
            
            # Final check to ensure it still looks like a valid config start after cleaning
            if cleaned_candidate and ConfigValidator.is_valid_protocol_prefix(cleaned_candidate):
                extracted_raw_configs.append(cleaned_candidate)
        
        return extracted_raw_configs


    @classmethod
    def validate_protocol_config(cls, config: str, protocol_name: str) -> bool:
        """
        Validates a config string based on its detected protocol.
        protocol_name should be like 'vmess', 'ss', not 'vmess://'.
        """
        try:
            # Ensure it starts with the correct prefix (reconstruct prefix from name)
            full_protocol_prefix = protocol_name + '://'
            if not config.startswith(full_protocol_prefix):
                return False

            if protocol_name == 'vmess':
                return cls.is_vmess_config(config)
            elif protocol_name == 'tuic':
                return cls.is_tuic_config(config)
            elif protocol_name == 'ss': # ss requires base64 encoded payload
                parts = config[len(full_protocol_prefix):].split('@')
                if len(parts) > 1: # Should have method:password@server:port part
                    return cls.is_base64(parts[0]) # Method:password part must be base64
                return False # Invalid SS format
            elif protocol_name == 'vless':
                # For VLESS, first check if it's a Reality config
                if cls.is_reality_config(config): # This will classify it as 'reality' later
                    return True # It's a valid VLESS (and Reality)
                # Then, check generic VLESS structure (UUID@host:port)
                parsed = urlparse(config)
                # Basic VLESS validation: must have UUID and network location
                # Example: vless://<UUID>@host:port
                uuid_match = re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', parsed.netloc.split('@')[0] if '@' in parsed.netloc else '')
                return bool(parsed.netloc and '@' in parsed.netloc and uuid_match)
            elif protocol_name in ['trojan', 'hysteria', 'hysteria2', 'wireguard', 'ssh', 'warp', 'juicity', 'http', 'https', 'socks5', 'mieru', 'snell', 'anytls']:
                # For many protocols, a basic URL parse and check for netloc (host:port) might suffice.
                parsed = urlparse(config)
                return bool(parsed.netloc) # Must have host:port

            return False
        except Exception:
            return False

