import re
import base64
import json
import os
import importlib
from typing import Optional, Tuple, List, Dict, Type, Union

from src.utils.settings_manager import settings
from src.utils.protocol_validators.base_validator import BaseValidator
# CHANGED: Import get_combined_protocol_full_regex
from src.utils.protocol_definitions import PROTOCOL_INFO_MAP, get_combined_protocol_full_regex


class ConfigValidator:
    def __init__(self):
        self.protocol_validators: Dict[str, Type[BaseValidator]] = self._load_protocol_validators()
        # CHANGED: Use the new full regex
        self.combined_protocol_full_regex = get_combined_protocol_full_regex()
        
        self._all_protocol_prefixes = {info["prefix"] for info in PROTOCOL_INFO_MAP.values() if isinstance(info["prefix"], str)}
        print("ConfigValidator: Initialized. Loaded protocol validators.")


    def _load_protocol_validators(self) -> Dict[str, Type[BaseValidator]]:
        # ... (این متد بدون تغییر باقی می‌ماند)
        validators_map: Dict[str, Type[BaseValidator]] = {}
        validator_dir = os.path.join(os.path.dirname(__file__), 'protocol_validators')

        for protocol_name, info in PROTOCOL_INFO_MAP.items():
            validator_class = info["validator"]
            if issubclass(validator_class, BaseValidator):
                validators_map[protocol_name] = validator_class
                print(f"ConfigValidator: Loaded validator for protocol '{protocol_name}': {validator_class.__name__}")
            else: 
                print(f"ConfigValidator: WARNING: Validator for protocol '{protocol_name}' is not a subclass of BaseValidator. Using generic BaseValidator.")
                validators_map[protocol_name] = BaseValidator
        
        return validators_map


    # --- Base64 Validation and Decoding (بدون تغییر) ---
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

    # --- Centralized Protocol Validation (بدون تغییر) ---
    def validate_protocol_config(self, config_link: str, protocol_name: str) -> bool:
        validator_class = self.protocol_validators.get(protocol_name)
        if validator_class:
            is_valid = validator_class.is_valid(config_link)
            if not is_valid:
                print(f"ConfigValidator: VALIDATION FAILED for protocol '{protocol_name}' on link: {config_link[:200]}...")
            return is_valid
        
        is_valid = self.is_valid_protocol_prefix(config_link)
        return is_valid

    # --- Centralized Protocol Cleaning (بدون تغییر) ---
    def clean_protocol_config(self, config_link: str, protocol_name: str) -> str:
        validator_class = self.protocol_validators.get(protocol_name)
        if validator_class and hasattr(validator_class, 'clean'):
            cleaned_link = validator_class.clean(config_link)
            return cleaned_link
        return config_link

    # --- General Cleaning and Splitting from Text (اصلاح شده) ---
    @staticmethod
    def clean_string_for_splitting(text: str) -> str:
        # ... (این متد بدون تغییر باقی می‌ماند)
        text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', text)
        text = text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def split_configs_from_text(self, text: str) -> List[str]:
        """
        Extracts all potential config strings from a larger text using the full protocol regex.
        """
        extracted_raw_configs: List[str] = []
        cleaned_full_text = self.clean_string_for_splitting(text)
        
        # CHANGED: Use findall with the full regex pattern
        # This will find ALL occurrences of full links, not just prefixes
        found_full_links = self.combined_protocol_full_regex.findall(cleaned_full_text)
        print(f"ConfigValidator: Found {len(found_full_links)} potential full links using combined regex.")

        for raw_link_candidate in found_full_links:
            # Apply trailing junk pattern to each found link
            trailing_junk_pattern = re.compile(
                r'(\s+[\d\U0001F000-\U0001FFFF\u2705-\u27BF\ufe00-\ufe0f]+.*|\s+Channel\s+https?:\/\/t\.me\/[a-zA-Z0-9_]+.*|' + 
                r'\s+برای سرور های جدید.*|' + 
                r'\s+اپراتورها.*|' + 
                r'\s+Tel\. Channel.*|' + 
                r'\s+\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*|' + 
                r'\s+#کانفیگ\s*#proxy\s*#vray.*|' + 
                r'\s+Test\s+on.*|' + 
                r'\s+برای دوستان خود ارسال کنید.*|' + 
                r'\s+وصله\s*\?|' + 
                r'\s+ایرانسل، مخابرات و رایتل.*|' + 
                r'\s+لطفاً دانلود نداشته باشید.*' +
                r'|\s+#\w+\s*#.*' +
                r'|\s+@\w+'
                , re.IGNORECASE | re.DOTALL
            )
            
            junk_match = trailing_junk_pattern.search(raw_link_candidate)
            if junk_match:
                final_config_str = raw_link_candidate[:junk_match.start()].strip()
                print(f"ConfigValidator: Stripped trailing junk from: '{raw_link_candidate[:50]}...' -> '{final_config_str[:50]}...'")
            else:
                final_config_str = raw_link_candidate.strip()

            if final_config_str: # Add if not empty after cleaning
                extracted_raw_configs.append(final_config_str)

        print(f"ConfigValidator: Finished splitting. Extracted {len(extracted_raw_configs)} raw config candidates.")
        return extracted_raw_configs

    def is_valid_protocol_prefix(self, config_str: str) -> bool:
        # ... (این متد بدون تغییر باقی می‌ماند)
        return any(config_str.startswith(p) for p in self._all_protocol_prefixes)