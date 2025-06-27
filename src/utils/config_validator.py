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
from src.utils.protocol_definitions import PROTOCOL_REGEX_MAP 

class ConfigValidator:
    # --- Base64 Validation and Decoding (UNCHANGED) ---
    @staticmethod
    def is_base64(s: str) -> bool:
        s_clean = s.rstrip('=')
        return bool(re.fullmatch(r'^[A-Za-z0-9+/_-]*$', s_clean))

    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        try:
            s_padded = s.replace('-', '+').replace('_', '/')
            padding = 4 - (len(s_padded) % 4)
            if padding != 4:
                s_padded += '=' * padding
            return base64.b64decode(s_padded)
        except Exception:
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
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

    # --- Basic Type/Format Validations (UNCHANGED) ---
    @staticmethod
    def is_valid_uuid(value: str) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False

    @staticmethod
    def is_valid_ip_address(ip: str) -> bool:
        if ip.startswith("[") and ip.endswith("]"):
            ip = ip[1:-1]
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_ipv6(ip: str) -> bool:
        if ip.startswith("[") and ip.endswith("]"):
            ip = ip[1:-1]
        try:
            return isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
        except ValueError:
            return False

    @staticmethod
    def is_valid_domain(hostname: str) -> bool:
        if not hostname or len(hostname) > 255:
            return False
        if hostname.endswith("."):
            hostname = hostname[:-1]
        return all(re.match(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$", x) for x in hostname.split("."))

    # --- Protocol-Specific Cleaning (UNCHANGED) ---
    @staticmethod
    def clean_vmess_config(config: str) -> str:
        if config.startswith("vmess://"):
            base64_part = config[8:]
            clean_base64_part_match = re.match(r'[A-Za-z0-9+/=_-]*', base64_part)
            if clean_base64_part_match:
                return f"vmess://{clean_base64_part_match.group(0).strip()}"
        return config

    @staticmethod
    def normalize_hysteria2_protocol(config: str) -> str:
        if config.startswith('hy2://'):
            return config.replace('hy2://', 'hysteria2://', 1)
        return config

    # --- Protocol-Specific Validation (TEMPORARILY MADE VERY PERMISSIVE) ---
    @staticmethod
    def is_vmess_config(config: str) -> bool:
        # TEMPORARY: Basic check for Vmess - just needs to start with vmess:// and have some length
        return config.startswith('vmess://') and len(config) > 20 # Minimal length check

    @staticmethod
    def is_tuic_config(config: str) -> bool:
        # TEMPORARY: Basic check for TUIC
        return config.startswith('tuic://') and len(config) > 20 # Minimal length check
    
    @staticmethod
    def is_reality_config(config: str) -> bool:
        # TEMPORARY: Basic check for Reality - just starts with vless:// and might have "reality" somewhere
        return config.startswith('vless://') and "reality" in config.lower() # Very basic check for presence of keyword

    @staticmethod
    def is_valid_protocol_prefix(config_str: str) -> bool:
        # TEMPORARY: Just checks if it starts with any known protocol prefix.
        return any(config_str.startswith(p + '://') for p in PROTOCOL_REGEX_MAP.keys())


    # --- General Cleaning and Splitting from Text (TEMPORARILY SIMPLIFIED) ---
    @staticmethod
    def clean_config_string(config_text: str) -> str:
        """
        Removes only common invisible/control characters and reduces excessive whitespace.
        This version is even LESS aggressive.
        """
        config_text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', config_text)
        config_text = config_text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        config_text = re.sub(r'\s+', ' ', config_text).strip() # Normalize whitespace
        return config_text

    @staticmethod
    def split_configs_from_text(text: str, protocols_regex: re.Pattern) -> List[str]:
        """
        Extracts all potential config strings from a larger text.
        TEMPORARY: This version is much simpler and relies heavily on newlines or double spaces.
        """
        extracted_raw_configs: List[str] = []
        
        # Apply minimal cleaning first
        cleaned_full_text = ConfigValidator.clean_config_string(text)
        
        # Split by newlines or by patterns that are unlikely to be *within* a config string.
        # This is a very permissive split.
        # It relies on the assumption that configs are usually on separate lines or clearly separated.
        # We will use the protocol prefix regex to find starts, then split.
        
        # Find all occurrences of known protocol prefixes.
        protocol_start_matches = list(protocols_regex.finditer(cleaned_full_text))
        
        if not protocol_start_matches:
            return []

        for i, match in enumerate(protocol_start_matches):
            start_index = match.start()
            
            end_of_current_config_candidate = len(cleaned_full_text)
            if i + 1 < len(protocol_start_matches):
                end_of_current_config_candidate = protocol_start_matches[i+1].start()
            
            # Extract the raw segment from current protocol start to next protocol start (or end of text)
            raw_segment = cleaned_full_text[start_index:end_of_current_config_candidate].strip()
            
            # Additional simple cleaning AFTER extraction of the segment
            # This is where we might strip off obvious trailing junk that's NOT part of the URL itself
            # Example: "ss://link#title 1️⃣ 📥" --> "ss://link#title"
            # Look for common patterns that appear *after* a config and signify its end.
            # This pattern is specifically designed to cut off common junk observed in your samples
            # like emojis, numbers, and specific Farsi/English text at the end of the line.
            # This is less aggressive than previous versions.
            trailing_junk_pattern = re.compile(
                r'(\s+[\d\U0001F000-\U0001FFFF\u2705-\u27BF\ufe00-\ufe0f]+.*|\s+Channel\s+https?:\/\/t\.me\/[a-zA-Z0-9_]+.*|' + # Numbers/Emojis/Channel links
                r'\s+برای سرور های جدید.*|' + # Farsi common phrase
                r'\s+اپراتورها.*|' + # Farsi common phrase
                r'\s+Tel\. Channel.*|' + # English common phrase
                r'\s+\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*|' + # Complex metadata
                r'\s+#کانفیگ\s*#proxy\s*#vray.*|' + # Hashtag block
                r'\s+Test\s+on.*|' + # "Test on..."
                r'\s+برای دوستان خود ارسال کنید.*|' + # Farsi call to action
                r'\s+وصله\s*\?|' + # Farsi question
                r'\s+ایرانسل، مخابرات و رایتل.*|' + # Farsi ISPs
                r'\s+لطفاً دانلود نداشته باشید.*' # Farsi instruction
                r'|\s+#\w+\s*#.*' # General #title #tag format (like from sample)
                r'|\s+@\w+' # Trailing @channel mention (e.g. from your example: @speeds_vpn)
                , re.IGNORECASE | re.DOTALL # re.DOTALL to match across newlines
            )
            
            # Apply protocol-specific cleaning first, THEN try to strip trailing junk.
            # This is to ensure internal base64/URL parts are not affected.
            final_config_str = raw_segment
            if final_config_str.startswith("vmess://"):
                final_config_str = ConfigValidator.clean_vmess_config(final_config_str)
            elif final_config_str.startswith("hy2://"):
                final_config_str = ConfigValidator.normalize_hysteria2_protocol(final_config_str)
            # Add other protocol-specific cleaning here if needed
            
            # Now, attempt to cut off trailing junk
            junk_match = trailing_junk_pattern.search(final_config_str)
            if junk_match:
                final_config_str = final_config_str[:junk_match.start()].strip()
            else:
                # If no specific junk pattern, simply strip leading/trailing whitespace
                final_config_str = final_config_str.strip()


            # Final check that it still looks like a valid config start after cleaning
            if final_config_str and ConfigValidator.is_valid_protocol_prefix(final_config_str):
                extracted_raw_configs.append(final_config_str)
        
        return extracted_raw_configs

