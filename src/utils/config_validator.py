# src/utils/config_validator.py

import re
import base64
import json
import uuid 
from typing import Optional, Tuple, List, Dict
from urllib.parse import unquote, urlparse, parse_qs
import ipaddress
import socket 

from src.utils.settings_manager import settings
from src.utils.protocol_definitions import PROTOCOL_REGEX_MAP # Import the base regex map

class ConfigValidator:
    # --- Base64 Validation and Decoding ---
    @staticmethod
    def is_base64(s: str) -> bool:
        """Checks if a string is a valid base64 (standard or URL-safe) string."""
        s_clean = s.rstrip('=')
        return bool(re.fullmatch(r'^[A-Za-z0-9+/_-]*$', s_clean))

    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        """Decodes a base64url string (with - and _)."""
        try:
            s_padded = s.replace('-', '+').replace('_', '/')
            padding = 4 - (len(s_padded) % 4)
            if padding != 4:
                s_padded += '=' * padding
            return base64.b64decode(s_padded, validate=True)
        except Exception:
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
        """Decodes a string that might be base64 encoded (standard or URL-safe), returning UTF-8 text."""
        try:
            decoded_bytes = base64.b64decode(text, validate=True)
            return decoded_bytes.decode('utf-8', errors='ignore')
        except Exception:
            try:
                decoded_bytes = ConfigValidator.decode_base64_url(text)
                if decoded_bytes:
                    return decoded_bytes.decode('utf-8', errors='ignore')
            except Exception:
                pass
        return None

    # --- Basic Type/Format Validations ---
    @staticmethod
    def is_valid_uuid(value: str) -> bool:
        """Checks if a string is a valid UUID."""
        try:
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False

    @staticmethod
    def is_valid_ip_address(ip: str) -> bool:
        """Checks if a string is a valid IPv4 or IPv6 address."""
        if ip.startswith("[") and ip.endswith("]"):
            ip = ip[1:-1] # Remove brackets for IPv6 addresses
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_ipv6(ip: str) -> bool:
        """Checks if a string is an IPv6 address."""
        if ip.startswith("[") and ip.endswith("]"):
            ip = ip[1:-1]
        try:
            return isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
        except ValueError:
            return False

    @staticmethod
    def is_valid_domain(hostname: str) -> bool:
        """Checks if a string is a valid domain name (basic check)."""
        if not hostname or len(hostname) > 255:
            return False
        if hostname.endswith("."): # strip exactly one dot from the end, if any
            hostname = hostname[:-1] 
        return all(re.match(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$", x) for x in hostname.split("."))

    # --- Protocol-Specific Cleaning ---
    @staticmethod
    def clean_vmess_config(config: str) -> str:
        """Cleans a Vmess link by stripping extra characters after base64 part."""
        if config.startswith("vmess://"):
            base64_part = config[8:]
            clean_base64_part_match = re.match(r'[A-Za-z0-9+/=_-]*', base64_part)
            if clean_base64_part_match:
                return f"vmess://{clean_base64_part_match.group(0).strip()}"
        return config

    @staticmethod
    def normalize_hysteria2_protocol(config: str) -> str:
        """Normalizes 'hy2://' to 'hysteria2://'."""
        if config.startswith('hy2://'):
            return config.replace('hy2://', 'hysteria2://', 1)
        return config

    # --- Protocol-Specific Validation ---
    @staticmethod
    def is_vmess_config(config: str) -> bool:
        """Validates if a string is a structurally valid Vmess config."""
        try:
            if not config.startswith('vmess://'):
                return False
            base64_part = config[8:]
            if len(base64_part) < 10: return False # Too short
            decoded = ConfigValidator.decode_base64_text(base64_part)
            if decoded:
                vmess_json = json.loads(decoded)
                return bool(vmess_json.get('v') and vmess_json.get('ps') and vmess_json.get('add') and vmess_json.get('port') and vmess_json.get('id'))
            return False
        except Exception:
            return False

    @staticmethod
    def is_tuic_config(config: str) -> bool:
        """Validates if a string is a structurally valid TUIC config (basic check)."""
        try:
            if not config.startswith('tuic://'):
                return False
            parsed = urlparse(config)
            # TUIC requires a UUID:password@ format often. Basic check on netloc.
            return bool(parsed.netloc and ':' in parsed.netloc)
        except Exception:
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
            
            host_part = parsed.netloc.split('@')[-1].split(':')[0] if '@' in parsed.netloc else parsed.netloc.split(':')[0]

            is_reality = (bool(parsed.netloc and ':' in parsed.netloc) and 
                          security_val == 'reality' and bool(pbk_val) and bool(sni_val) and 
                          (ConfigValidator.is_valid_domain(host_part) or ConfigValidator.is_valid_ip_address(host_part)))
            
            return is_reality
        except Exception:
            return False


    @staticmethod
    def is_valid_protocol_prefix(config_str: str) -> bool:
        """Checks if a string starts with any protocol prefix from PROTOCOL_REGEX_MAP."""
        # Using a pre-compiled regex for efficiency for common prefixes
        # It's safer to check against the keys of PROTOCOL_REGEX_MAP directly.
        # This will be used for splitting, so it should be general.
        return bool(re.match(r'^[a-zA-Z0-9]+\:\/\/', config_str))


    # --- General Cleaning and Splitting from Text (Revised) ---
    @staticmethod
    def clean_config_string(config_text: str) -> str:
        """
        Removes common non-printable characters and reduces excessive whitespace.
        This version is less aggressive on emojis/numbers which might serve as delimiters.
        """
        # Remove common invisible/control characters (including ZWJ, ZWNJ, BOM, etc.)
        config_text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', config_text)
        
        # Remove specific HTML entity artifacts (like &amp;)
        config_text = config_text.replace('&amp;', '&')
        config_text = config_text.replace('&gt;', '>').replace('&lt;', '<') # In case of HTML entities for < or >

        # Normalize whitespace (multiple spaces to single, and strip leading/trailing)
        config_text = re.sub(r'\s+', ' ', config_text).strip()
        
        return config_text

    @staticmethod
    def split_configs_from_text(text: str, protocols_regex: re.Pattern) -> List[str]:
        """
        Extracts all potential config strings from a larger text, handling concatenations
        and junk characters between configs.
        """
        extracted_raw_configs: List[str] = []
        
        # Apply general cleaning first to make regex matching more reliable
        cleaned_full_text = ConfigValidator.clean_config_string(text)

        # Find all occurrences of known protocol prefixes in the cleaned text
        matches = list(protocols_regex.finditer(cleaned_full_text))
        
        if not matches:
            return []

        # Pattern for common delimiters that signify the end of a config.
        # This is CRUCIAL for robust splitting.
        # It looks for:
        # 1. Newline or multiple spaces (>= 2)
        # 2. Common emojis/symbols often used as separators (e.g., checkmarks, arrows, numbers with squares)
        # 3. Specific Farsi/English phrases/metadata that often follow a config.
        # This list needs to be comprehensive based on observed data.
        end_delimiters_pattern = re.compile(
            r'\s{2,}|\n|' # Two or more spaces, or a newline
            r'[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+|' # Common emojis/symbols
            r'\d{1,2}[\uFE0F\u20E3]?\s*[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\ufe00-\ufe0f\u200b-\u200d\uFEFF\u200e\u200f\u202a-\u202e\u2066-\u2069]+|' # Numbers with emojis (e.g., 5️⃣ 📥)
            r'\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*ᴄᴏᴜɴᴛʀʏ:\s*#.*[a-zA-Z0-9]+\s*\([A-Z]{2}\)\s*ᴄᴏɴғɪɢsʜᴜʙ\s*₪\s*ᴀʀɪʏᴀ\s*₪\s*ʙᴏᴛ\s*₪\s*ʜᴇʟᴘ|' + # Complex channel metadata
            r'Channel\s*https:\/\/t\.me\/[a-zA-Z0-9_]+|' + # 'Channel https://t.me/...'
            r'برای سرور های جدید داخل چنل زیر عضو بشید Channel https:\/\/t\.me\/[a-zA-Z0-9_]+|' + # Farsi specific discovery text
            r'اپراتورها\s*@\w+|' + # 'اپراتورها @channel'
            r'@\w+\s*[🔺👇]+|' + # '@channel 🔺👇'
            r'#کانفیگ\s*#proxy\s*#vray|' + # Hashtag blocks
            r'Tel\.\s*Channel|' + # 'Tel. Channel'
            r'برای دوستان خود ارسال کنید|' + # Farsi call to action
            r'وصله\s*\؟|' + # Farsi question "connected?"
            r'ایرانسل، مخابرات و رایتل|' + # Farsi text
            r'تست شده روی مخابرات و همراه اول|' + # Farsi text
            r'لطفاً دانلود نداشته باشید\s*\/\s*برای اتصال تا یک دقیقه صبر کنید\s*\.|' + # Farsi instruction
            r'اینترنت\s*پروکسی_رایگان\s*کانال رو معرفی و شیر کنین\s*@\w+|' + # Farsi text with channel
            r'حتما\s*vrayng\s*رو به نسخه اخر آپدیت کنین\.|' + # Farsi instructions
            r'اگه کاربر ios هستید، از اپ Streisand و Vbox استفاده کنید\.|' + # Farsi instructions
            r'\s+MCI\s+&.*@\w+' # MCI &... @channel
            , re.IGNORECASE | re.DOTALL # re.DOTALL to match across newlines
        )

        for i, match in enumerate(matches):
            start_index = match.start()
            
            # Determine the end of the current config candidate
            candidate_segment_end_index = -1
            if i + 1 < len(matches):
                # End is the start of the next config
                candidate_segment_end_index = matches[i+1].start()
            else:
                # Last config, consider the rest of the text
                candidate_segment_end_index = len(cleaned_full_text)
            
            # Extract the raw segment between current and next protocol prefix
            raw_config_candidate_segment = cleaned_full_text[start_index:candidate_segment_end_index].strip()

            # Now, apply the end_delimiters_pattern to this segment to find the actual end of the current config
            # This handles cases where junk is immediately after a config but before the next protocol prefix.
            match_actual_end = end_delimiters_pattern.search(raw_config_candidate_segment)
            
            final_config_str = ""
            if match_actual_end:
                final_config_str = raw_config_candidate_segment[:match_actual_end.start()].strip()
            else:
                final_config_str = raw_config_candidate_segment # No specific delimiter found, take the whole segment

            # Apply protocol-specific cleaning based on its detected start
            if final_config_str.startswith("vmess://"):
                final_config_str = ConfigValidator.clean_vmess_config(final_config_str)
            elif final_config_str.startswith("hy2://"):
                final_config_str = ConfigValidator.normalize_hysteria2_protocol(final_config_str)
            # Add other protocol-specific cleaning here if needed
            
            # Final check to ensure it still looks like a valid config start after cleaning
            if final_config_str and ConfigValidator.is_valid_protocol_prefix(final_config_str):
                extracted_raw_configs.append(final_config_str)
        
        return extracted_raw_configs

