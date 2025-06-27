# src/utils/config_validator.py

import re
import base64
import json
import uuid # For UUID validation
from typing import Optional, Tuple, List, Dict
from urllib.parse import unquote, urlparse, parse_qs
import ipaddress # For IP address validation
import socket # For basic hostname to IP lookup if needed

# Import settings and protocol definitions
from src.utils.settings_manager import settings
from src.utils.protocol_definitions import PROTOCOL_REGEX_MAP 


class ConfigValidator:
    # --- Base64 Validation and Decoding (improved from provided sample) ---
    @staticmethod
    def is_base64(s: str) -> bool:
        """Checks if a string is a valid base64 (standard or URL-safe) string."""
        s_clean = s.rstrip('=')
        # Combined regex for standard base64 and base64url characters
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
        # This function could be replaced by tldextract if installed
        # For now, a basic regex check
        if not hostname or len(hostname) > 255:
            return False
        if hostname[-1] == ".":
            hostname = hostname[:-1] # strip exactly one dot from the end, if any
        return all(re.match(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$", x) for x in hostname.split("."))

    # --- Protocol-Specific Cleaning ---
    @staticmethod
    def clean_vmess_config(config: str) -> str:
        """Cleans a Vmess link by stripping extra characters after base64 part."""
        if config.startswith("vmess://"):
            base64_part = config[8:]
            # Find the end of base64 part by looking for non-base64 chars or end of string
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
                # Basic checks for essential Vmess fields
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
            # TUIC usually needs UUID and password, but this basic check only verifies network location
            # A stronger check would involve regex for UUID:password@
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
            
            # Must have host:port and security=reality and pbk and sni
            # Also, check the host part of the netloc for domain/IP validity
            host_part = parsed.netloc.split('@')[-1].split(':')[0] if '@' in parsed.netloc else parsed.netloc.split(':')[0]

            is_reality = (bool(parsed.netloc and ':' in parsed.netloc) and 
                          security_val == 'reality' and bool(pbk_val) and bool(sni_val) and 
                          (ConfigValidator.is_valid_domain(host_part) or ConfigValidator.is_valid_ip_address(host_part)))
            
            return is_reality
        except Exception:
            return False

    @staticmethod
    def is_valid_protocol_prefix(config_str: str) -> bool:
        """Checks if a string starts with a known protocol prefix from PROTOCOL_REGEX_MAP (e.g., 'ss://')."""
        return any(config_str.startswith(p + '://') for p in PROTOCOL_REGEX_MAP.keys())


    # --- General Cleaning and Splitting from Text ---
    # NEW: Revised clean_config_string - much less aggressive, focuses on non-printable/control chars
    @staticmethod
    def clean_config_string(config_text: str) -> str:
        """
        Removes common non-printable characters and reduces excessive whitespace.
        It is now much less aggressive to preserve actual config data.
        """
        # Remove common invisible/control characters (including ZWJ, ZWNJ, BOM)
        config_text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF]', '', config_text)
        
        # Remove specific HTML entity artifacts (like &amp;)
        config_text = config_text.replace('&amp;', '&')
        config_text = config_text.replace('&gt;', '>').replace('&lt;', '<') # In case of HTML entities for < or >

        # Normalize whitespace (multiple spaces to single, and strip leading/trailing)
        config_text = re.sub(r'\s+', ' ', config_text).strip()
        
        return config_text

    # NEW: Revised split_configs_from_text - robust splitting logic
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

        for i, match in enumerate(matches):
            start_index = match.start()
            end_index = -1

            if i + 1 < len(matches):
                # The end of current config is the start of the next one
                end_index = matches[i+1].start()
            else:
                # Last config, goes till the end of the text
                end_index = len(cleaned_full_text)
            
            # Extract the raw candidate string
            raw_config_candidate = cleaned_full_text[start_index:end_index].strip()
            
            # Additional end-of-config detection for the extracted segment.
            # This regex identifies common patterns that signify the end of a config URL/string
            # even if there's no space before the next one.
            # This pattern is crucial for cutting off junk like emojis, numbers, or specific text patterns
            # that appear *after* a valid config link ends.
            end_of_config_pattern = re.compile(
                r'(\s{2,}|\n|' # two or more spaces, or a newline
                r'[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]|' + # Common emojis and symbols
                r'\d{1,2}[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF])' + # Number + emoji (e.g., 5️⃣)
                r'|\s+Tel\.\s+Channel' # Specific text like ' Tel. Channel'
                r'|\s*Channel\s+https:\/\/t\.me\/[a-zA-Z0-9_]+' # 'Channel https://t.me/...'
                r'|\s*برای سرور های جدید داخل چنل زیر عضو بشید Channel https:\/\/t\.me\/[a-zA-Z0-9_]+' # Farsi specific
                r'|\s+اپراتورها\s+@\w+' # 'اپراتورها @channel'
                r'|\s*#کانفیگ\s*#proxy\s*#vray' # Hashtag blocks
                r'|\s*#\w+\s+\([A-Z]{2}\)\s*ᴄᴏɴғɪɢsʜᴜʙ' # Complex metadata like your example
                r'|\s+Channel id: @\w+' # Channel id: @channel
                r'|\s+MCI\s+&.*@\w+' # MCI &... @channel
                r'|\s+برای دوستان خود ارسال کنید' # Farsi call to action
                r'|\s+وصله ؟' # Farsi question
                r'|\s+ایرانسل، مخابرات و رایتل' # Farsi text
                r'|\s+تست شده روی مخابرات و همراه اول' # Farsi text
                r'|\s+لطفاً دانلود نداشته باشید \/ برای اتصال تا یک دقیقه صبر کنید \.' # Farsi instruction
                r'|\s+اینترنت\s+پروکسی_رایگان\s+کانال رو معرفی و شیر کنین\s+@\w+' # Farsi text with channel
                r'|\s+حتما\s+vrayng\s+رو به نسخه اخر آپدیت کنین' # Farsi instructions
                r'|\s+اگه کاربر ios هستید، از اپ Streisand و Vbox استفاده کنید.' # Farsi instructions
            )
            
            match_end = end_of_config_pattern.search(raw_config_candidate)
            if match_end:
                raw_config_candidate = raw_config_candidate[:match_end.start()].strip()
            
            # One final cleaning pass after splitting
            final_cleaned_candidate = ConfigValidator.clean_config_string(raw_config_candidate)
            
            if final_cleaned_candidate and ConfigValidator.is_valid_protocol_prefix(final_cleaned_candidate):
                extracted_raw_configs.append(final_cleaned_candidate)
        
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
                    return cls.is_base64(parts[0]) # Method:password part must be base64
                return False # Invalid SS format
            elif protocol_name == 'vless':
                # For VLESS, first check if it's a Reality config
                if cls.is_reality_config(config): # This will classify it as 'reality' later
                    return True # It's a valid VLESS (and Reality)
                # Then, check generic VLESS structure (UUID@host:port)
                parsed = urlparse(config)
                # Basic VLESS validation: must have UUID and network location
                if not (parsed.netloc and '@' in parsed.netloc): return False
                uuid_str = parsed.netloc.split('@')[0]
                return cls.is_valid_uuid(uuid_str)
            elif protocol_name in ['trojan', 'hysteria', 'hysteria2', 'wireguard', 'ssh', 'warp', 'juicity', 'http', 'https', 'socks5', 'mieru', 'snell', 'anytls']:
                # For many protocols, a basic URL parse and check for netloc (host:port) might suffice.
                parsed = urlparse(config)
                # A basic check: ensure it has a network location (host:port)
                # And for protocols that commonly use TLS, check for security=tls/reality/etc. in params if present.
                return bool(parsed.netloc)

            return False
        except Exception:
            return False

