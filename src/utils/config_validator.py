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
        s_stripped = s.strip()
        # Heuristic 1: Minimum length for a meaningful base64 string
        if len(s_stripped) < 10: # Very short strings are unlikely to be configs
            # print(f"ConfigValidator.is_base64: Rejected (too short): '{s_stripped}'")
            return False

        # Heuristic 2: Check for typical base64 characters.
        # Ensure it strictly adheres to base64 alphabet characters plus optional '=' padding.
        if not re.fullmatch(r'^[A-Za-z0-9+/_-]*={0,2}$', s_stripped): # {0,2} for up to two padding characters
            # print(f"ConfigValidator.is_base64: Rejected (invalid chars found or malformed padding): '{s_stripped[:50]}...'")
            return False

        # Heuristic 3: Attempt actual decoding to confirm it's decodable base64, but without raising error.
        try:
            # Try both standard and URL-safe decoding
            base64.b64decode(s_stripped, validate=True)
            # print(f"ConfigValidator.is_base64: PASSED (standard b64): '{s_stripped[:50]}...'")
            return True
        except Exception:
            try:
                s_padded = s_stripped.replace('-', '+').replace('_', '/')
                # Ensure correct padding for standard b64decode
                missing_padding = len(s_padded) % 4
                if missing_padding != 0:
                    s_padded += '=' * (4 - missing_padding)
                base64.b64decode(s_padded, validate=True)
                # print(f"ConfigValidator.is_base64: PASSED (url-safe b64): '{s_padded[:50]}...'")
                return True
            except Exception:
                # print(f"ConfigValidator.is_base64: Rejected (not decodable b64): '{s_stripped[:50]}...'")
                pass
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
        # Remove common zero-width spaces, control characters, etc.
        text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u200D\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', text)
        # Convert common HTML entities (&amp;, &gt;, &lt;)
        text = text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        # Normalize all whitespace characters (space, tab, newline) to a single space and strip leading/trailing
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
            # The pattern is ordered from most specific to more general.
            trailing_junk_pattern = re.compile(
                r'(\s*[\d\U0001F000-\U0001FFFF\u2705-\u27BF\ufe00-\ufe0f\u2600-\u26FF\u2700-\u27BF]+\s*.*|' + # Numbers/Emojis/Checkmarks/Stars and anything after
                r'\s*(?:Channel|برای سرور های جدید|اپراتورها|Tel\. Channel|Test on|برای دوستان خود ارسال کنید|وصله\?|ایرانسل، مخابرات و رایتل|لطفاً دانلود نداشته باشید|مسئله این است که جغرافیا زورش زیاد است|کم باش!اصلا هم نگران کم شدنت نباش!|پربرکت باشید)\s*.*|' + # Farsi/English common phrases
                r'\s*\[\s*\]t\.me\/[a-zA-Z0-9_]+\s*ϟ.*|' + # Complex metadata like [ ]t.me/... ϟ
                r'\s*#\w+\s*#.*|' + # Hashtag block like #سرور #فیلترشکن
                r'\s*@\w+\s*.*|' + # Trailing @channel mention
                r'|\s*(?:ᴄᴏᴜɴᴛʀʏ:|CREATOR:).*|' + # Country/Creator metadata
                r'|\s*\|\s*.*|' + # Pipe separators and anything after (e.g. from your example: "|")
                r'|\s*\S+\s*$' # Loosely match trailing single words or non-whitespace characters at end of line (like "✅" or "👌")
                , re.IGNORECASE | re.DOTALL | re.UNICODE # Re-added re.UNICODE for better emoji handling
            )
            
            final_config_str = raw_link_candidate.strip() # Initial strip

            junk_match = trailing_junk_pattern.search(final_config_str)
            if junk_match:
                original_len = len(final_config_str)
                final_config_str = final_config_str[:junk_match.start()].strip()
                # if final_config_str != raw_link_candidate.strip(): # Only log if something was actually stripped
                    # print(f"ConfigValidator: Stripped trailing junk from: '{raw_link_candidate[:50]}...' -> Cleaned: '{final_config_str[:50]}...' (original len: {original_len}, final len: {len(final_config_str)})")
            
            if final_config_str: # Add if not empty after cleaning
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