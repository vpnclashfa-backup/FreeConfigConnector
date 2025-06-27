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
            s_clean = s.rstrip('=')
            return bool(re.match(r'^[A-Za-z0-9+/\-_]*$', s_clean))
        except:
            return False

    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        """Decodes a base64url string (with - and _)."""
        try:
            s_padded = s.replace('-', '+').replace('_', '/')
            padding = 4 - (len(s_padded) % 4)
            if padding != 4:
                s_padded += '=' * padding
            return base64.b64decode(s_padded)
        except:
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
        """Decodes a string that might be base64 encoded, returning UTF-8 text."""
        try:
            decoded_bytes = base64.b64decode(text, validate=True)
            return decoded_bytes.decode('utf-8', errors='ignore')
        except:
            try:
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
            # Vmess base64 part should end with valid base64 chars, often followed by a display name (encoded)
            # Or it might end abruptly if concatenated.
            # We are more permissive here to not truncate valid parts of the UUID/JSON.
            return f"vmess://{base64_part.split(' ')[0].split('#')[0].strip()}" # Strip after first space or hash
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
            # A valid Vmess base64 part should not be extremely short and should be decodable.
            if len(base64_part) < 10: return False # Too short to be meaningful
            decoded = ConfigValidator.decode_base64_text(base64_part)
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
                return bool(parsed.netloc and ':' in parsed.netloc)
            return False
        except:
            return False
    
    @staticmethod
    def is_reality_config(config: str) -> bool:
        """
        Validates if a VLESS config includes valid Reality parameters.
        Reality needs: security=reality, pbk, sni.
        """
        try:
            if not config.startswith('vless://'):
                return False
            
            parsed = urlparse(config)
            query_params = parse_qs(parsed.query)
            
            security_val = query_params.get('security', [''])[0].lower()
            pbk_val = query_params.get('pbk', [''])[0]
            sni_val = query_params.get('sni', [''])[0]
            
            # Must have host:port and security=reality and pbk and sni
            is_reality = (bool(parsed.netloc and ':' in parsed.netloc) and 
                          security_val == 'reality' and bool(pbk_val) and bool(sni_val))
            
            return is_reality
        except Exception:
            return False


    @staticmethod
    def is_valid_protocol_prefix(config_str: str) -> bool:
        """Checks if a string starts with a known protocol prefix from PROTOCOL_REGEX_MAP (e.g., 'ss://')."""
        return any(config_str.startswith(p + '://') for p in PROTOCOL_REGEX_MAP.keys())


    # NEW: Revised clean_config_string - much less aggressive
    @staticmethod
    def clean_config_string(config: str) -> str:
        """
        Removes only truly unwanted characters that would break URL parsing or are purely cosmetic.
        This is now much less aggressive to preserve actual config data.
        """
        # Remove common Farsi/Arabic joining characters that affect string integrity
        config = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF]', '', config)
        
        # Remove specific problematic sequences like "amp;" introduced by HTML parsing errors
        config = config.replace('&amp;', '&')

        # Keep emojis and numbers for now, they will be used as delimiters in split_configs_from_text
        # Or handled by the regex itself in split.
        
        # Reduce multiple spaces to single space and strip leading/trailing whitespace
        config = re.sub(r'\s+', ' ', config).strip()
        
        return config


    # NEW: Revised split_configs_from_text - more robust splitting logic
    @staticmethod
    def split_configs_from_text(text: str, protocols_regex: re.Pattern) -> List[str]:
        """
        Extracts all potential config strings from a larger text, handling concatenations
        and junk characters between configs.
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
                end_index = matches[i+1].start()
            else:
                end_index = len(text) # Goes to end of string if last match
            
            raw_config_candidate = text[start_index:end_index].strip()
            
            # NEW: More robust end-of-config detection for the extracted segment.
            # Look for common delimiters that signify the end of a config
            # (e.g., newline, multiple spaces, specific emojis, numbers followed by space/emoji)
            # This regex is specifically designed to cut off junk *after* a config
            # and before the start of a next config or end of message.
            end_delimiters_pattern = re.compile(
                r'(\s{2,}|\n|' # two or more spaces, or a newline
                r'[\U0001F600-\U0001F64F\U00002600-\U000027BF\ufe00-\ufe0f\d{1,2}\ufe0f?\s*[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002190-\U000021FF\U00002300-\U000023FF\U000024C2\U000025AA-\U000025FE\U00002600-\U000026FF\U00002700-\U000027BF\u200B-\u200D\uFE0F\u200C-\u200D\uFE0F]*[\s\uFEFF\u200B-\u200D\u200E\u200F\u202F\u205F\u00A0\u2000-\u200A\u3000\u0009\u000A\u000B\u000C\u000D\u0085\u2028\u2029\u1680\u200B\u200C\u200D\u200E\u200F\u202F\u205F\u3000\u00A0\u180E\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u200B-\u200D\u200E-\u200F\u2028-\u2029\u205F\u3000\u000D\u000A]+|\d{1,2}[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF])' # Numbers with emojis
                r'|\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*ᴄᴏᴜɴᴛʀʏ: #.*[a-zA-Z0-9]+' # Specific channel metadata string like your example
                r'|Channel\s+https:\/\/t\.me\/[a-zA-Z0-9_]+' # Channel ID/link string
                r'|برای سرور های جدید داخل چنل زیر عضو بشید Channel https:\/\/t\.me\/[a-zA-Z0-9_]+' # Farsi subscription string
                r'|^\s* اپراتورها\s*[\U0001F600-\U0001F64F\u200B-\u200D\uFE0F\s]*@\w+' # "اپراتورها @channel"
                r'|@\w+\s*[🔺👇]' # Channel mention followed by down arrows
                r'|#[\w\d_]+\s*#proxy\s*#vray' # Hashtag block like yours
                r'|\s+Tel\.\s+Channel' # common text
                r'|^\s*[\u200B-\u200D\uFE0F\s]*\d+\s*[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]|\s*[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF])+|\s*✅' # Another attempt to catch leading numbers/emojis and checkmarks
                r'|\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ\s*ᴇsғᴀʜᴀɴ\s*ϟ\s*ᴄᴏᴜɴᴛʀʏ:\s*#.*[\U0001F1E6-\U0001F1FF]+\s*\([A-Z]{2}\)\s*ᴄᴏɴғɪɢsʜᴜʙ\s*₪\s*ᴀʀɪʏᴀ\s*₪\s*ʙᴏᴛ\s*₪\s*ʜᴇʟᴘ' # Full complex metadata example
            )
            
            match = end_delimiters_pattern.search(raw_config_candidate)
            if match:
                raw_config_candidate = raw_config_candidate[:match.start()].strip()
            
            # Now, apply protocol-specific cleaning based on its detected start
            cleaned_candidate = raw_config_candidate # Start with current cleaned candidate
            if cleaned_candidate.startswith("vmess://"):
                cleaned_candidate = ConfigValidator.clean_vmess_config(cleaned_candidate)
            elif cleaned_candidate.startswith("hy2://"):
                cleaned_candidate = ConfigValidator.normalize_hysteria2_protocol(cleaned_candidate)
            # Add other protocol-specific cleaning here if needed
            
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
            full_protocol_prefix = protocol_name + '://'
            if not config.startswith(full_protocol_prefix):
                return False

            if protocol_name == 'vmess':
                return cls.is_vmess_config(config)
            elif protocol_name == 'tuic':
                return cls.is_tuic_config(config)
            elif protocol_name == 'ss': # ss requires base64 encoded payload
                parts = config[len(full_protocol_prefix):].split('@')
                if len(parts) > 1:
                    return cls.is_base64(parts[0])
                return False
            elif protocol_name == 'vless':
                # For VLESS, first check if it's a Reality config
                if cls.is_reality_config(config):
                    return True # It's a valid VLESS (and Reality)
                # Then, check generic VLESS structure (UUID@host:port)
                parsed = urlparse(config)
                # Basic VLESS validation: must have UUID and network location
                uuid_match = re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', parsed.netloc.split('@')[0] if '@' in parsed.netloc else '')
                return bool(parsed.netloc and '@' in parsed.netloc and uuid_match)
            elif protocol_name in ['trojan', 'hysteria', 'hysteria2', 'wireguard', 'ssh', 'warp', 'juicity', 'http', 'https', 'socks5', 'mieru', 'snell', 'anytls']:
                # For many protocols, a basic URL parse and check for netloc (host:port) might suffice.
                parsed = urlparse(config)
                return bool(parsed.netloc)

            return False
        except Exception:
            return False

