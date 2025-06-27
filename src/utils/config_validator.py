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
        return bool(re.fullmatch(r'^[A-Za-z0-9+/\-_]*$', s_clean))

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
        return any(config_str.startswith(p + '://') for p in PROTOCOL_REGEX_MAP.keys())


    # --- General Cleaning and Splitting from Text (Revised) ---
    @staticmethod
    def clean_config_string(config_text: str) -> str:
        """
        Removes only truly unwanted characters that would break URL parsing or are purely cosmetic.
        This is now much less aggressive to preserve actual config data.
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
        # This gives us the starting points of potential configs.
        protocol_start_matches = list(protocols_regex.finditer(cleaned_full_text))
        
        if not protocol_start_matches:
            return []

        # This regex identifies common patterns that signify the end of a config.
        # It needs to be very precise to avoid cutting off valid parts of a URL
        # while effectively separating junk.
        # Characters allowed in URL path, query, fragment: a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=
        # We look for a clear break:
        # - Two or more spaces, or a newline
        # - The start of another protocol (lookahead)
        # - Common visual separators / emojis that are NOT part of a valid URL character set
        # - Specific phrases indicating end of config or start of new section.

        # A non-greedy match of any character up to a delimiter or next protocol start.
        # We need to make sure the regex in protocol_definitions.py is general enough to *start* the match,
        # and then this splitting logic *finds the end* of that started match.
        
        # Let's simplify the split logic: capture everything until the next protocol start, or end of string.
        # Then, apply *post-processing* to strip common junk from the *end* of the captured string.
        # This is often more reliable than complex "end-of-config" lookaheads.

        # Combined protocol prefix pattern for finding *next* config
        # (This is the same as protocols_regex passed in)
        
        for i, match in enumerate(protocol_start_matches):
            start_index = match.start()
            
            end_of_current_config_candidate = len(cleaned_full_text)
            if i + 1 < len(protocol_start_matches):
                end_of_current_config_candidate = protocol_start_matches[i+1].start()
            
            # Extract the segment from current protocol start to next protocol start (or end of text)
            raw_segment = cleaned_full_text[start_index:end_of_current_config_candidate].strip()
            
            # Now, refine the end of this segment. This is where we cut off trailing junk.
            # Define common junk patterns that come *after* a config but are *not* part of the next config.
            # This regex is specifically tailored for the junk observed in your samples.
            junk_at_end_pattern = re.compile(
                r'(\s*#\s*✅\s*@\w+|' + # # ✅ @channelname
                r'\s*\d+[\uFE0F\u20E3]?\s*[\U0001F600-\U0001F9FF\u2705-\u27BF\ufe00-\ufe0f]+|' + # Number + emoji/symbol (e.g., 6️⃣ 📥)
                r'\s*#کانفیگ\s*#proxy\s*#vray.*|' + # Hashtag block
                r'\s*اپراتورها\s*@\w+.*|' + # اپراتورها @channel
                r'\s*برای سرور های جدید داخل چنل زیر عضو بشید Channel https:\/\/t\.me\/[a-zA-Z0-9_]+.*|' + # Farsi discovery phrase
                r'\s*Channel\s*https:\/\/t\.me\/[a-zA-Z0-9_]+.*|' + # Channel https://t.me/...
                r'\s*Telegram\s*\|\s*@\w+.*|' + # Telegram | @channel
                r'\s*✔️سرور جدید V2ray.*|' + # Specific intro phrase
                r'\s*روی سرور زیر انگشت بزنید،همگی کپی می‌شوند.*|' + # Farsi instruction
                r'\s*✅لطفاً دانلود نداشته باشید \/ برای اتصال تا یک دقیقه صبر کنید \s*\.|' + # Farsi instruction
                r'\s*🌐@Canfing_VPN \| به اشتراک بگذارید.*|' + # Farsi ending with channel
                r'\s*---------------.*|' + # Horizontal line
                r'\s*🔳\s*@\w+.*|' + # Box emoji + channel
                r'\s*\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*ᴄᴏᴜɴᴛʀʏ:.*|' + # Complex metadata
                r'\s*#\s+IR.*\s*:\s*$|' + # SS example suffix
                r'\s+#\s*\w+.*\s*\d+[\u2705-\U0001FAFF]+|' + # SS example suffix with checkmark
                r'\s+#\s*(\S+)\s*\d+[\U0001F600-\U0001F64F\u2705-\u27BF\ufe00-\ufe0f]+.*|' + # #title 5️⃣📥
                r'\s+.*برای دوستان خود ارسال کنید.*|' + # Farsi call to action
                r'\s+همراه اول وصله' + # Farsi phrases
                r'\s+ایران سل وصله' + # Farsi phrases
                r'\s+اینترنت ایرانسل' + # Farsi phrases
                r'\s+برای کانفیگ های جدید عضو شوید.*' # Farsi call to action
                , re.IGNORECASE | re.DOTALL # Match across newlines
            )
            
            # Search for the junk pattern from the *end* of the raw_segment, backwards, or from a known start.
            # A more robust way: find the first occurrence of junk *after* the protocol prefix
            # but *before* the next protocol prefix.
            
            # Take the current segment and try to cut off junk from its end
            cleaned_segment = raw_segment
            junk_match = junk_at_end_pattern.search(raw_segment)
            if junk_match:
                cleaned_segment = raw_segment[:junk_match.start()].strip()
            
            # Apply protocol-specific cleaning. This step should be very focused on URL structure.
            if cleaned_segment.startswith("vmess://"):
                cleaned_segment = ConfigValidator.clean_vmess_config(cleaned_segment)
            elif cleaned_segment.startswith("hy2://"):
                cleaned_segment = ConfigValidator.normalize_hysteria2_protocol(cleaned_segment)
            # Add other protocol-specific cleaning here if needed
            
            if cleaned_segment and ConfigValidator.is_valid_protocol_prefix(cleaned_segment):
                extracted_raw_configs.append(cleaned_segment)
        
        return extracted_raw_configs

