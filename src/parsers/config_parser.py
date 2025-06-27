# src/parsers/config_parser.py

import base64
import json
import re
import yaml # pip install PyYAML
from typing import List, Dict, Optional, Tuple # Added Tuple
from urllib.parse import unquote, urlparse

# NEW: Inline ConfigValidator class (can be moved to src/utils/config_validator.py if preferred)
class ConfigValidator:
    @staticmethod
    def is_base64(s: str) -> bool:
        """Checks if a string is a valid base64 (or base64url) string."""
        try:
            s_clean = s.rstrip('=') # Remove padding for validation
            # Base64url alphabet uses - and _ instead of + and /
            return bool(re.match(r'^[A-Za-z0-9+/_-]*$', s_clean))
        except:
            return False

    @staticmethod
    def decode_base64_url(s: str) -> Optional[bytes]:
        """Decodes a base64url string (with - and _)."""
        try:
            s_padded = s.replace('-', '+').replace('_', '/') # Convert to standard base64 alphabet
            padding = 4 - (len(s_padded) % 4)
            if padding != 4: # Only add padding if necessary
                s_padded += '=' * padding
            return base64.b64decode(s_padded, validate=True)
        except:
            return None

    @staticmethod
    def decode_base64_text(text: str) -> Optional[str]:
        """Decodes a string that might be base64 encoded, returning UTF-8 text."""
        try:
            # Try to decode as standard base64 first
            decoded_bytes = base64.b64decode(text, validate=True)
            return decoded_bytes.decode('utf-8', errors='ignore')
        except:
            try:
                # If standard fails, try base64url
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
            # Find the end of base64 part by looking for non-base64 chars or end of string
            clean_base64_part = re.match(r'[A-Za-z0-9+/=_-]*', base64_part)
            if clean_base64_part:
                return f"vmess://{clean_base64_part.group(0).strip()}"
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
            decoded = ConfigValidator.decode_base64_text(base64_part) # Use general text decoder
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
                # Basic check: should have a network location (host:port)
                return bool(parsed.netloc and ':' in parsed.netloc)
            return False
        except:
            return False

    @staticmethod
    def is_valid_protocol_prefix(text: str, protocols: List[str]) -> bool:
        """Checks if text starts with any of the given protocol prefixes."""
        return any(text.startswith(p) for p in protocols)

    @staticmethod
    def clean_config_string(config: str) -> str:
        """
        Removes common junk characters, emojis, and excessive whitespace from a config string.
        """
        # Remove common emojis and non-printable characters
        config = re.sub(r'[\U0001F300-\U0001F6FF\U00002600-\U000027BF\ufe00-\ufe0f\u200b-\u200d\uFEFF\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', config)
        # Remove numbers with circle Unicode variations (e.g., 1️⃣, 2️⃣)
        config = re.sub(r'\d{1,2}\ufe0f?', '', config)
        # Remove common Farsi/Arabic joining characters or repeated symbols like 🛜 ❓ ❗️ 🔤 etc
        config = re.sub(r'[\u200c-\u200f\u0600-\u0605\u061B-\u061F\u064B-\u065F\u0670\u06D6-\u06DD\u06DF-\u06ED\u06F0-\u06F9\u200B-\u200F\u0640\u202A-\u202E\u2066-\u2069\uFE00-\uFE0F\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\ufeff\u200d\s]*[\u2705\u2714\u274c\u274e\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002190-\U000021FF\U00002300-\U000023FF\U000024C2\U000025AA-\U000025FE\U00002600-\U000026FF\U00002700-\U000027BF\u200B-\u200D\uFE0F\u200C-\u200D\uFE0F]*[\s\uFEFF\u200B-\u200D\u200E\u200F\u202F\u205F\u00A0\u2000-\u200A\u3000\u0009\u000A\u000B\u000C\u000D\u0085\u2028\u2029\u1680\u200B\u200C\u200D\u200E\u200F\u202F\u205F\u3000\u00A0\u180E\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200A\u200B-\u200D\u200E-\u200F\u2028-\u2029\u205F\u3000\u000D\u000A]+', '', config).strip()
        # Remove any remaining unwanted characters (e.g., from your sample: 5️⃣ 📥)
        config = re.sub(r'[\u2460-\u2469\u24EA\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2705\u2714\u274c\u274e\u26A0\u26A1\u26D4\u26C4\u26F0-\u26F5\u26FA\u26FD\u2700-\u27BF\u23F3\u231B\u23F8-\u23FA\u2B50\u2B55\u25AA\u25AB\u25FB\u25FC\u25FD\u25FE\u2B1B\u2B1C\u274C\u274E\u2753\u2754\u2755\u2795\u2796\u2797\u27B0\u27BF\u2934\u2935\u2B06\u2B07\u2B1B\u2B1C\u2B50\u2B55\u2BFF\U0001F0CF\U0001F170-\U0001F171\U0001F17E-\U0001F17F\U0001F18E\U0001F1F0\U0001F1F0-\U0001F1FF\U0001F200-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]+', '', config)
        config = re.sub(r'\s+', ' ', config) # Reduce multiple spaces to single space
        return config.strip()

    @staticmethod
    def is_valid_config_start(config_str: str) -> bool:
        """Checks if a string starts with a known protocol prefix."""
        protocols = ['vmess://', 'vless://', 'ss://', 'trojan://', 'hysteria://', 'hysteria2://', 'hy2://', 'tuic://', 'wireguard://', 'ssh://', 'warp://', 'juicity://', 'http://', 'https://', 'socks5://', 'ssconf://']
        return any(config_str.startswith(p) for p in protocols)


    @classmethod
    def validate_protocol_config(cls, config: str, protocol: str) -> bool:
        """Validates a config string based on its detected protocol."""
        try:
            if not config.startswith(protocol):
                return False

            if protocol == 'vmess://':
                return cls.is_vmess_config(config)
            elif protocol == 'tuic://':
                return cls.is_tuic_config(config)
            elif protocol in ['ss://', 'vless://', 'trojan://', 'hysteria://', 'hysteria2://', 'hy2://', 'wireguard://', 'ssh://', 'warp://', 'juicity://', 'http://', 'https://', 'socks5://', 'ssconf://']:
                # For many protocols, a basic URL parse and check for network location might suffice
                # or ensure it decodes if it's base64 encoded.
                parsed = urlparse(config)
                if not parsed.netloc: # Must have host:port
                    return False
                
                # For protocols that might have base64 encoded payloads (e.g., ss, vless sometimes)
                # We can try to decode part of it if it looks like base64.
                # Example: for ss:// base64encoded@host:port
                if protocol == 'ss://':
                    parts = config[5:].split('@') # Skip ss://
                    if len(parts) > 1 and cls.is_base64(parts[0]):
                        return True
                    return False # ss must have base64 part
                
                # Basic check for other protocols: just ensure it's a valid URL-like string
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def split_configs_from_text(text: str, protocols_regex: re.Pattern) -> List[str]:
        """
        Extracts all potential config strings from a larger text, handling concatenations.
        Uses a combined regex to find all protocol starts and then extracts the content
        between starts.
        """
        extracted_raw_configs: List[str] = []
        
        matches = list(protocols_regex.finditer(text))
        
        if not matches:
            return []

        for i, match in enumerate(matches):
            start_index = match.start()
            end_index = -1

            if i + 1 < len(matches):
                end_index = matches[i+1].start()
            else:
                end_index = len(text)
            
            raw_config_candidate = text[start_index:end_index].strip()
            
            # Clean before adding. This cleaning removes junk that might be *within* a config.
            cleaned_candidate = ConfigValidator.clean_config_string(raw_config_candidate)
            
            if cleaned_candidate and ConfigValidator.is_valid_config_start(cleaned_candidate):
                extracted_raw_configs.append(cleaned_candidate)
        
        return extracted_raw_configs


from src.utils.settings_manager import settings
# Combined regex for all active protocols, compiled once for efficiency
_combined_active_protocol_regex = re.compile(
    '|'.join([re.escape(p + '://') for p in settings.ACTIVE_PROTOCOLS if p != 'ssconf']), # ssconf is a special case
    re.IGNORECASE
)

class ConfigParser:
    def __init__(self):
        self.protocol_regex_patterns = get_config_regex_patterns()
        self.config_validator = ConfigValidator() # Instantiate the validator
        # Compile patterns for efficiency
        self.compiled_patterns = {
            p: re.compile(pattern, re.IGNORECASE) 
            for p, pattern in self.protocol_regex_patterns.items()
        }
        # A combined regex pattern to find ANY known protocol link. This is for splitting
        self.combined_protocol_regex = re.compile(
            '|'.join([re.escape(pattern_prefix) for pattern_prefix in self.protocol_regex_patterns.keys()]), # Use keys directly, e.g., 'ss://'
            re.IGNORECASE
        )

    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        Extracts direct protocol links from any given text.
        This function now uses _split_configs_from_text from ConfigValidator
        to first break down the text into valid config-like strings.
        """
        found_links: List[Dict] = []
        
        # Use the validator's split method to get potential clean config strings
        config_candidates = self.config_validator.split_configs_from_text(text_content, self.combined_protocol_regex)

        for candidate in config_candidates:
            # Try to match each candidate against specific protocol patterns
            for protocol, compiled_pattern in self.compiled_patterns.items():
                if compiled_pattern.match(candidate): # Use match() to check from start of string
                    # Validate the extracted config more deeply
                    if self.config_validator.validate_protocol_config(candidate, protocol):
                        found_links.append({'protocol': protocol, 'link': candidate})
                        break # Move to the next candidate once a valid match is found
        
        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """Attempts to decode base64 content using ConfigValidator's method."""
        if not settings.ENABLE_BASE64_DECODING:
            return None
        
        decoded_str = self.config_validator.decode_base64_text(content)
        if decoded_str:
            # Check if decoded content looks like a list of links or another parsable format
            if len(decoded_str) > 10 and (self.combined_protocol_regex.search(decoded_str) or 
                                          self.config_validator.is_valid_config_start(decoded_str)):
                print("Successfully decoded Base64 content and it contains potential links.")
                return decoded_str
            print("Base64 decoded, but content does not appear to contain configs or valid protocol links.")
            return None
        return None

    def _parse_clash_config(self, content: str) -> List[Dict]:
        """
        Parses Clash YAML configurations to extract proxy links.
        """
        if not settings.ENABLE_CLASH_PARSER:
            return []
        
        extracted_links: List[Dict] = []
        try:
            clash_data = yaml.safe_load(content)
            if not isinstance(clash_data, dict):
                return []

            # Extract from 'proxies' list
            proxies = clash_data.get('proxies', [])
            for proxy_obj in proxies:
                if isinstance(proxy_obj, dict):
                    # Attempt to reconstruct SS/SSR links from dict, then validate
                    if proxy_obj.get('type', '').lower() == 'ss' and all(k in proxy_obj for k in ['cipher', 'password', 'server', 'port']):
                        try:
                            method_pass = f"{proxy_obj['cipher']}:{proxy_obj['password']}"
                            encoded_method_pass = base64.b64encode(method_pass.encode()).decode()
                            ss_link = f"ss://{encoded_method_pass}@{proxy_obj['server']}:{proxy_obj['port']}"
                            if 'name' in proxy_obj: ss_link += f"#{proxy_obj['name']}"
                            if self.config_validator.validate_protocol_config(ss_link, 'ss://'):
                                extracted_links.append({'protocol': 'ss', 'link': ss_link})
                        except Exception as e:
                            print(f"Error reconstructing SS link from Clash: {e}")
                    
                    # For other types (vmess, vless, trojan), they are often direct links or complex.
                    # We rely on searching the JSON string representation for direct protocol links.
                    proxy_str_representation = json.dumps(proxy_obj)
                    extracted_links.extend(self._extract_direct_links(proxy_str_representation))


            # Extract from 'proxy-providers' (URLs pointing to subscriptions)
            proxy_providers = clash_data.get('proxy-providers', {})
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
                    # Check if the URL is a valid http/https URL and add as a subscription source
                    if provider_obj['url'].startswith('http://') or provider_obj['url'].startswith('https://'):
                        extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})
            
            print("Successfully parsed Clash config and extracted potential links.")
        except yaml.YAMLError:
            pass
        except Exception as e:
            print(f"Error parsing Clash config: {e}")
        return extracted_links

    def _parse_singbox_config(self, content: str) -> List[Dict]:
        """
        Parses SingBox JSON configurations to extract proxy links/outbounds.
        """
        if not settings.ENABLE_SINGBOX_PARSER:
            return []
        
        extracted_links: List[Dict] = []
        try:
            singbox_data = json.loads(content)
            if not isinstance(singbox_data, dict):
                return []

            outbounds = singbox_data.get('outbounds', [])
            for outbound_obj in outbounds:
                if isinstance(outbound_obj, dict):
                    # Convert outbound object to string to search for links like vmess://, vless://
                    outbound_str = json.dumps(outbound_obj)
                    extracted_links.extend(self._extract_direct_links(outbound_str))
                        
            print("Successfully parsed SingBox config and extracted potential links.")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error parsing SingBox config: {e}")
        return extracted_links

    def _parse_json_content(self, content: str) -> List[Dict]:
        """
        Parses general JSON content to find any embedded config links or subscription URLs.
        """
        if not settings.ENABLE_JSON_PARSER:
            return []

        extracted_links: List[Dict] = []
        try:
            json_data = json.loads(content)
            json_string = json.dumps(json_data)
            extracted_links.extend(self._extract_direct_links(json_string))
            print("Successfully parsed general JSON content and extracted potential links.")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error parsing general JSON content: {e}")
        return extracted_links


    def parse_content(self, content: str) -> List[Dict]:
        """
        Attempts to parse the given content and extract config links using various methods.
        Returns a list of {'protocol': '...', 'link': '...'} dictionaries.
        """
        all_extracted_links: List[Dict] = []
        
        # 1. Try to extract direct links first from the raw content
        direct_links = self._extract_direct_links(content)
        all_extracted_links.extend(direct_links)
        
        # 2. Try Base64 decoding and then parse the decoded content
        decoded_content = self._decode_base64(content)
        if decoded_content:
            # First, extract direct links from decoded content
            base64_links = self._extract_direct_links(decoded_content)
            all_extracted_links.extend(base64_links)
            
            # Then, try to parse decoded content as Clash/SingBox/general JSON
            all_extracted_links.extend(self._parse_clash_config(decoded_content))
            all_extracted_links.extend(self._parse_singbox_config(decoded_content))
            all_extracted_links.extend(self._parse_json_content(decoded_content))


        # 3. Try Clash (YAML) parsing from raw content
        clash_links = self._parse_clash_config(content)
        all_extracted_links.extend(clash_links)

        # 4. Try SingBox (JSON) parsing from raw content
        singbox_links = self._parse_singbox_config(content)
        all_extracted_links.extend(singbox_links)

        # 5. Try general JSON parsing from raw content
        json_links = self._parse_json_content(content)
        all_extracted_links.extend(json_links)
        
        # Deduplicate extracted links before returning
        return list({link['link']: link for link in all_extracted_links}.values())
