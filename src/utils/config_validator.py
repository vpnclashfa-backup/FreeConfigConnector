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
        # Load all protocol validators dynamically
        self.protocol_validators: Dict[str, Type[BaseValidator]] = self._load_protocol_validators()
        # CHANGED: Use the new full regex
        self.combined_protocol_full_regex = get_combined_protocol_full_regex()
        
        self._all_protocol_prefixes = {info["prefix"] for info in PROTOCOL_INFO_MAP.values() if isinstance(info["prefix"], str)}
        print("ConfigValidator: Initialized. Loaded protocol validators.")


    def _load_protocol_validators(self) -> Dict[str, Type[BaseValidator]]:
        """
        Validatorهای مخصوص پروتکل را به صورت داینامیک از دایرکتوری protocol_validators/ بارگذاری می‌کند.
        """
        validators_map: Dict[str, Type[BaseValidator]] = {}
        # Changed to iterate directly through PROTOCOL_INFO_MAP to avoid filesystem scanning dependency
        for protocol_name, info in PROTOCOL_INFO_MAP.items():
            validator_class = info["validator"]
            if issubclass(validator_class, BaseValidator): # Ensure it's a valid validator class
                validators_map[protocol_name] = validator_class
                print(f"ConfigValidator: Loaded validator for protocol '{protocol_name}': {validator_class.__name__}") # Log each loaded validator
            else: 
                print(f"ConfigValidator: WARNING: Validator for protocol '{protocol_name}' is not a subclass of BaseValidator. Using generic BaseValidator.") # Warning for incorrect validator
                validators_map[protocol_name] = BaseValidator
        
        return validators_map


    # --- Base64 Validation and Decoding (UNCHANGED logic, added logs) ---
    @staticmethod
    def is_base64(s: str) -> bool:
        """
        Checks if a string is a valid base64 sequence (can contain URL-safe chars).
        This is a loose check to see if it's WORTH trying to decode.
        """
        s_clean = s.rstrip('=')
        is_b64 = bool(re.fullmatch(r'^[A-Za-z0-9+/_-]*$', s_clean))
        # if not is_b64: print(f"ConfigValidator.is_base64: String '{s[:50]}...' is NOT a valid base64 character set.") # Too verbose, but useful for debugging
        return is_b64

    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        """Decodes URL-safe base64 string."""
        try:
            s_padded = s.replace('-', '+').replace('_', '/')
            padding = 4 - (len(s_padded) % 4)
            if padding != 4:
                s_padded += '=' * padding
            return base64.b64decode(s_padded)
        except Exception as e:
            # print(f"ConfigValidator.decode_base64_url: Failed to decode URL-safe base64 '{s[:50]}...': {e}") # Debug specific reason
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
        """Attempts to decode a string as standard base64, then as URL-safe base64."""
        # print(f"ConfigValidator.decode_base64_text: Attempting to decode text (len={len(text)}).") # Too verbose
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
        # print(f"ConfigValidator.decode_base64_text: Failed for '{text[:50]}...'.") # Too verbose
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
                print(f"ConfigValidator: VALIDATION FAILED for protocol '{protocol_name}' on link: {config_link[:200]}...") # Log failed validation
            return is_valid
        
        # Fallback for unknown protocols, or protocols without specific validators
        # This will only check if it starts with a known prefix.
        is_valid = self.is_valid_protocol_prefix(config_link)
        if not is_valid:
            print(f"ConfigValidator: Fallback validation failed for protocol '{protocol_name}' (link doesn't start with known prefix): {config_link[:200]}...")
        # else:
            # print(f"ConfigValidator: No specific validator for '{protocol_name}'. Fallback prefix check PASSED for: {config_link[:100]}...") # Too verbose
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
                # print(f"ConfigValidator: Cleaned '{protocol_name}' link. Original: '{config_link[:50]}...' -> Cleaned: '{cleaned_link[:50]}...'") # Log if changed, too verbose
                pass
            return cleaned_link
        # print(f"ConfigValidator: No specific cleaner for '{protocol_name}'. Returning original link: '{config_link[:50]}...'") # Too verbose
        return config_link


    # --- General Cleaning and Splitting from Text (MODIFIED logic, added logs) ---
    @staticmethod
    def clean_string_for_splitting(text: str) -> str:
        """
        Removes common invisible/control characters, HTML entities, and reduces excessive whitespace
        to prepare text for splitting. This is a preliminary cleaning.
        """
        # Remove common zero-width spaces, control characters, etc.
        text = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFEFF\u0000-\u001F\u007F-\u009F]', '', text)
        # Convert common HTML entities (&amp;, &gt;, &lt;)
        text = text.replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<')
        # Normalize all whitespace characters (space, tab, newline) to a single space and strip leading/trailing
        text = re.sub(r'\s+', ' ', text).strip() 
        # print(f"ConfigValidator: Cleaned preliminary text (length {len(text)}).") # Too verbose
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

        # CHANGED: Use findall with the full regex pattern
        # This will find ALL occurrences of full links, not just prefixes.
        # It's crucial for extracting links embedded in longer text.
        found_full_links_candidates = self.combined_protocol_full_regex.findall(cleaned_full_text)
        print(f"ConfigValidator: Found {len(found_full_links_candidates)} potential full link candidates using combined regex.")
        # if found_full_links_candidates: print(f"ConfigValidator: First candidate: '{found_full_links_candidates[0][:100]}...'") # Detailed

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
                r'|\s+@\w+' # Trailing @channel mention (e.g. from your example: @speeds_vpn)
                , re.IGNORECASE | re.DOTALL # re.DOTALL to match across newlines if text is multi-line
            )
            
            final_config_str = raw_link_candidate.strip() # Initial strip

            junk_match = trailing_junk_pattern.search(final_config_str)
            if junk_match:
                original_len = len(final_config_str)
                final_config_str = final_config_str[:junk_match.start()].strip()
                print(f"ConfigValidator: Stripped trailing junk. Original (len={original_len}): '{raw_link_candidate[:50]}...' -> Cleaned (len={len(final_config_str)}): '{final_config_str[:50]}...'")
            # else:
                # print(f"ConfigValidator: No trailing junk found for: '{raw_link_candidate[:50]}...'") # Too verbose

            if final_config_str: # Add if not empty after cleaning
                extracted_raw_configs.append(final_config_str)
            else:
                print(f"ConfigValidator: Candidate '{raw_link_candidate[:50]}...' became EMPTY after cleaning. Not added.")

        print(f"ConfigValidator: Finished splitting. Extracted {len(extracted_raw_configs)} raw config candidates after cleaning.")
        return extracted_raw_configs

    def is_valid_protocol_prefix(self, config_str: str) -> bool:
        """
        بررسی می‌کند که آیا یک رشته با هر پیشوند پروتکل شناخته شده‌ای شروع می‌شود یا خیر.
        """
        # print(f"ConfigValidator: Checking prefix for '{config_str[:50]}...'") # Too verbose
        return any(config_str.startswith(p) for p in self._all_protocol_prefixes)