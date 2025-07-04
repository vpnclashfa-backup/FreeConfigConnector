import re
import base64
import json
import os
import importlib
from typing import Optional, Tuple, List, Dict, Type, Union

from src.utils.settings_manager import settings
from src.utils.protocol_validators.base_validator import BaseValidator
from src.utils.protocol_definitions import PROTOCOL_INFO_MAP, get_combined_protocol_full_regex


class ConfigValidator:
    def __init__(self):
        self.protocol_validators: Dict[str, Type[BaseValidator]] = self._load_protocol_validators()
        self.combined_protocol_full_regex = get_combined_protocol_full_regex()
        
        self._all_protocol_prefixes = {info["prefix"] for info in PROTOCOL_INFO_MAP.values() if isinstance(info["prefix"], str)}
        print("ConfigValidator: Initialized. Loaded protocol validators.")


    def _load_protocol_validators(self) -> Dict[str, Type[BaseValidator]]:
        validators_map: Dict[str, Type[BaseValidator]] = {}
        for protocol_name, info in PROTOCOL_INFO_MAP.items():
            validator_class = info["validator"]
            if issubclass(validator_class, BaseValidator):
                validators_map[protocol_name] = validator_class
                print(f"ConfigValidator: Loaded validator for protocol '{protocol_name}': {validator_class.__name__}")
            else: 
                print(f"ConfigValidator: WARNING: Validator for protocol '{protocol_name}' is not a subclass of BaseValidator. Using generic BaseValidator.")
                validators_map[protocol_name] = BaseValidator
        
        return validators_map


    # --- Base64 Validation and Decoding (IMPROVED heuristic for is_base64, added logs) ---
    @staticmethod
    def is_base64(s: str) -> bool:
        """
        Checks if a string is a valid base64 character set (loose check).
        Aims to quickly discard strings that are definitely not base64.
        """
        # A quick check for common non-base64 characters or very short strings unlikely to be configs.
        # Base64 strings should typically be longer than a few characters.
        # This heuristic tries to prevent trying to decode short emojis or random text.
        if len(s) < 10 or not re.search(r'^[a-zA-Z0-9+/_-]*=?=?$', s): # Must strictly adhere to base64 charset + padding
            # print(f"ConfigValidator.is_base64: Rejected (short/invalid base64 charset): '{s[:50]}...'")
            return False

        # Attempt actual decoding to confirm it's decodable base64, but without raising error.
        try:
            # Try both standard and URL-safe decoding
            base664.b64decode(s, validate=True)
            return True
        except Exception:
            try:
                s_padded = s.replace('-', '+').replace('_', '/')
                missing_padding = len(s_padded) % 4
                if missing_padding != 0:
                    s_padded += '=' * (4 - missing_padding)
                base64.b64decode(s_padded, validate=True)
                return True
            except Exception:
                # print(f"ConfigValidator.is_base64: Rejected (not decodable base64): '{s[:50]}...'")
                return False


    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        """Decodes URL-safe base64 string."""
        try:
            s_padded = s.replace('-', '+').replace('_', '/')
            # Ensure correct padding for standard b64decode
            padding = 4 - (len(s_padded) % 4)
            if padding != 4:
                s_padded += '=' * (4 - padding)
            return base64.b64decode(s_padded)
        except Exception as e:
            # print(f"ConfigValidator.decode_base64_url: Failed to decode URL-safe base64 '{s[:50]}...': {e}")
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
        """Attempts to decode a string as standard base64, then as URL-safe base64."""
        # print(f"ConfigValidator.decode_base64_text: Attempting to decode text (len={len(text)}).")
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
        # print(f"ConfigValidator.decode_base64_text: Failed for '{text[:50]}...'.")
        return None

    # --- Centralized Protocol Validation (Dispatcher Logic, added logs) ---
    def validate_protocol_config(self, config_link: str, protocol_name: str) -> bool:
        """
        اعتبارسنجی یک لینک کانفیگ با استفاده از Validator مخصوص پروتکل.
        """
        validator_class = self.protocol_validators.get(protocol_name)
        if validator_class:
            is_valid = validator_class.is_valid(config_link)
            if not is_valid:
                print(f"ConfigValidator: VALIDATION FAILED for protocol '{protocol_name}' on link: {config_link[:200]}...")
            # else:
                # print(f"ConfigValidator: Validation PASSED for protocol '{protocol_name}' on link: {config_link[:100]}...")
            return is_valid
        
        # Fallback for unknown protocols, or protocols without specific validators
        is_valid = self.is_valid_protocol_prefix(config_link)
        if not is_valid:
            print(f"ConfigValidator: Fallback validation FAILED for protocol '{protocol_name}' (link doesn't start with known prefix): {config_link[:200]}...")
        return is_valid


    # --- Centralized Protocol Cleaning (Dispatcher Logic, added logs) ---
    def clean_protocol_config(self, config_link: str, protocol_name: str) -> str:
        """
        پاکسازی یک لینک کانفیگ با استفاده از Cleaner مخصوص پروتکل.
        """
        validator_class = self.protocol_validators.get(protocol_name)
        if validator_class and hasattr(validator_class, 'clean'):
            cleaned_link = validator_class.clean(config_link)
            if cleaned_link != config_link: 
                # print(f"ConfigValidator: Cleaned '{protocol_name}' link. Original: '{config_link[:50]}...' -> Cleaned: '{cleaned_link[:50]}...'")
                pass
            return cleaned_link
        return config_link

    # --- General Cleaning and Splitting from Text (IMPROVED logic, added logs) ---
    @staticmethod
    def clean_string_for_splitting(text: str) -> str:
        """
        Removes common invisible/control characters, HTML entities, and reduces excessive whitespace
        to prepare text for splitting. This is a preliminary cleaning.
        """
        text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', text)
        text = text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        text = re.sub(r'\s+', ' ', text).strip() 
        return text

    def split_configs_from_text(self, text: str) -> List[str]:
        """
        Extracts all potential full config strings from a larger text using the combined_protocol_full_regex.
        Each extracted candidate then undergoes a secondary trailing junk removal.
        """
        extracted_raw_configs: List[str] = []
        cleaned_full_text = self.clean_string_for_splitting(text)
        
        if not cleaned_full_text:
            print("ConfigValidator: Cleaned text is empty after preliminary cleaning. No candidates to extract.")
            return []

        found_full_links_candidates = self.combined_protocol_full_regex.findall(cleaned_full_text)
        print(f"ConfigValidator: Found {len(found_full_links_candidates)} potential full link candidates using combined regex.")


        for raw_link_candidate in found_full_links_candidates:
            # Apply trailing junk pattern to each found link. This is a crucial secondary cleaning.
            # This pattern is specifically designed to cut off common junk observed in your samples
            # like emojis, numbers, and specific Farsi/English text at the end of the line.
            trailing_junk_pattern = re.compile(
                r'(\s+[\d\U0001F000-\U0001FFFF\u2705-\u27BF\ufe00-\ufe0f]+.*|' + # Numbers/Emojis/Checkmarks/Stars and anything after
                r'\s+Channel\s+https?:\/\/t\.me\/[a-zA-Z0-9_]+.*|' + # "Channel https://t.me/..."
                r'\s+برای سرور های جدید.*|' + # Farsi common phrase
                r'\s+اپراتورها.*|' + # Farsi common phrase
                r'\s+Tel\. Channel.*|' + # English common phrase
                r'\s+\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*|' + # Complex metadata like [ ]t.me/... ϟ
                r'\s+#کانفیگ\s*#proxy\s*#vray.*|' + # Hashtag block
                r'\s+Test\s+on.*|' + # "Test on..."
                r'\s+برای دوستان خود ارسال کنید.*|' + # Farsi call to action
                r'\s+وصله\s*\?|' + # Farsi question
                r'\s+ایرانسل، مخابرات و رایتل.*|' + # Farsi ISPs
                r'\s+لطفاً دانلود نداشته باشید.*|' + # Farsi instruction
                r'|\s+#\w+\s*#.*|' + # General #title #tag format (like from sample)
                r'|\s+ᴄᴏᴜɴᴛʀʏ:.*|' + # Added for country text in your samples
                r'|\s+CREATOR:.*|' + # Added for creator text in your samples
                r'|\s+@\w+' + # Trailing @channel mention
                r'|\s*[\u2600-\u26FF\u2700-\u27BF\U0001F000-\U0001FFFF]+\s*.*|' + # Catch any lingering emojis at the end
                r'|\s*\S+\s*$' # Loosely match trailing single words or non-whitespace characters at end of line (like "✅" or "👌")
                , re.IGNORECASE | re.DOTALL
            )
            
            final_config_str = raw_link_candidate.strip() # Initial strip

            junk_match = trailing_junk_pattern.search(final_config_str)
            if junk_match:
                original_len = len(final_config_str)
                final_config_str = final_config_str[:junk_match.start()].strip()
                # if final_config_str != raw_link_candidate.strip():
                    # print(f"ConfigValidator: Stripped trailing junk from: '{raw_link_candidate[:50]}...' -> Cleaned: '{final_config_str[:50]}...' (original len: {original_len}, final len: {len(final_config_str)})")
            
            if final_config_str:
                extracted_raw_configs.append(final_config_str)
            else:
                print(f"ConfigValidator: Candidate '{raw_link_candidate[:50]}...' became EMPTY after cleaning. Not added to extracted configs.")

        print(f"ConfigValidator: Finished splitting. Extracted {len(extracted_raw_configs)} raw config candidates after all cleaning.")
        return extracted_raw_configs

    def is_valid_protocol_prefix(self, config_str: str) -> bool:
        """
        Checks if a string starts with any known protocol prefix.
        Used as a basic fallback or quick check.
        """
        return any(config_str.startswith(p) for p in self._all_protocol_prefixes)