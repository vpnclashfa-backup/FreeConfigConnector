import re
import base64
import json
import os
import importlib
from typing import Optional, Tuple, List, Dict, Type

from src.utils.settings_manager import settings
# NEW: Import the BaseValidator and PROTOCOL_INFO_MAP
from src.utils.protocol_validators.base_validator import BaseValidator
from src.utils.protocol_definitions import PROTOCOL_INFO_MAP, get_combined_protocol_prefix_regex


class ConfigValidator:
    def __init__(self):
        # Load all protocol validators dynamically
        self.protocol_validators: Dict[str, Type[BaseValidator]] = self._load_protocol_validators()
        self.combined_protocol_prefix_regex = get_combined_protocol_prefix_regex()
        
        # Keep _all_protocol_prefixes for generic checks or when a specific validator isn't loaded
        # This will now use PROTOCOL_INFO_MAP prefixes.
        self._all_protocol_prefixes = {info["prefix"] for info in PROTOCOL_INFO_MAP.values() if isinstance(info["prefix"], str)}


    def _load_protocol_validators(self) -> Dict[str, Type[BaseValidator]]:
        """
        Validatorهای مخصوص پروتکل را به صورت داینامیک از دایرکتوری protocol_validators/ بارگذاری می‌کند.
        """
        validators_map: Dict[str, Type[BaseValidator]] = {}
        validator_dir = os.path.join(os.path.dirname(__file__), 'protocol_validators')

        # Iterate through PROTOCOL_INFO_MAP to find the correct validator class
        for protocol_name, info in PROTOCOL_INFO_MAP.items():
            validator_class = info["validator"]
            if issubclass(validator_class, BaseValidator): # Ensure it's a valid validator class
                validators_map[protocol_name] = validator_class
            else: 
                print(f"Warning: Validator for protocol '{protocol_name}' is not a subclass of BaseValidator. Using generic BaseValidator.")
                validators_map[protocol_name] = BaseValidator
        
        return validators_map


    # --- Base64 Validation and Decoding (UNCHANGED - these are generic and stay here) ---
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

    # --- Protocol-Specific Cleaning (REMOVED - now handled by protocol-specific validators) ---
    # clean_vmess_config, normalize_hysteria2_protocol were already removed in step 4

    # --- Centralized Protocol Validation (Dispatcher Logic - UNCHANGED from Step 4) ---
    def validate_protocol_config(self, config_link: str, protocol_name: str) -> bool:
        """
        اعتبارسنجی یک لینک کانفیگ با استفاده از Validator مخصوص پروتکل.
        """
        validator_class = self.protocol_validators.get(protocol_name)
        if validator_class:
            return validator_class.is_valid(config_link)
        
        # Fallback for unknown protocols, or protocols without specific validators
        # This uses a very basic check if no specific validator is found
        return self.is_valid_protocol_prefix(config_link) # Check if it at least starts with a known prefix


    # --- Centralized Protocol Cleaning (Dispatcher Logic - UNCHANGED from Step 4) ---
    def clean_protocol_config(self, config_link: str, protocol_name: str) -> str:
        """
        پاکسازی یک لینک کانفیگ با استفاده از Cleaner مخصوص پروتکل.
        """
        validator_class = self.protocol_validators.get(protocol_name)
        # Ensure the validator class has a 'clean' method (BaseValidator enforces this, but a safety check doesn't hurt)
        if validator_class and hasattr(validator_class, 'clean'):
            return validator_class.clean(config_link)
        return config_link # Return original if no specific cleaner is found


    # --- General Cleaning and Splitting from Text (UNCHANGED from Step 4) ---
    @staticmethod
    def clean_string_for_splitting(text: str) -> str:
        """
        Removes common invisible/control characters and reduces excessive whitespace
        to prepare text for splitting. This is a preliminary cleaning.
        """
        text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', text)
        text = text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        text = re.sub(r'\s+', ' ', text).strip() # Normalize whitespace
        return text

    def split_configs_from_text(self, text: str) -> List[str]:
        """
        Extracts all potential config strings from a larger text based on protocol prefixes.
        This method will use the combined regex from protocol_definitions and
        then attempt to strip trailing junk.
        """
        extracted_raw_configs: List[str] = []

        # Apply minimal cleaning first
        cleaned_full_text = self.clean_string_for_splitting(text)

        # Find all occurrences of known protocol prefixes.
        protocol_start_matches = list(self.combined_protocol_prefix_regex.finditer(cleaned_full_text))

        if not protocol_start_matches:
            return []

        for i, match in enumerate(protocol_start_matches):
            start_index = match.start()

            end_of_current_config_candidate = len(cleaned_full_text)
            if i + 1 < len(protocol_start_matches):
                end_of_current_config_candidate = protocol_start_matches[i+1].start()

            # Extract the raw segment from current protocol start to next protocol start (or end of text)
            raw_segment = cleaned_full_text[start_index:end_of_current_config_candidate].strip()

            # This pattern is specifically designed to cut off common junk observed in your samples
            # like emojis, numbers, and specific Farsi/English text at the end of the line.
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
                , re.IGNORECASE | re.DOTALL
            )

            # Attempt to cut off trailing junk
            junk_match = trailing_junk_pattern.search(raw_segment)
            if junk_match:
                final_config_str = raw_segment[:junk_match.start()].strip()
            else:
                final_config_str = raw_segment.strip()

            # Final check that it still looks like a valid config start after cleaning
            if final_config_str and self.is_valid_protocol_prefix(final_config_str):
                extracted_raw_configs.append(final_config_str)

        return extracted_raw_configs

    def is_valid_protocol_prefix(self, config_str: str) -> bool:
        """
        بررسی می‌کند که آیا یک رشته با هر پیشوند پروتکل شناخته شده‌ای شروع می‌شود یا خیر.
        """
        return any(config_str.startswith(p) for p in self._all_protocol_prefixes)