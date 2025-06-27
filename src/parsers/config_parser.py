# src/parsers/config_parser.py

import base64
import json
import re
import yaml # pip install PyYAML
from typing import List, Dict, Optional, Tuple # Ensure Tuple is imported
from urllib.parse import unquote, urlparse # Only if still needed directly here

# NEW: Import from centralized protocol definitions
from src.utils.protocol_definitions import get_protocol_regex_patterns, get_combined_protocol_regex
# NEW: Import the standalone ConfigValidator
from src.utils.config_validator import ConfigValidator

# Re-using settings directly from utils
from src.utils.settings_manager import settings


class ConfigParser:
    def __init__(self):
        # Use get_protocol_regex_patterns from centralized definitions
        self.protocol_regex_patterns_map = get_protocol_regex_patterns()
        self.config_validator = ConfigValidator() # Instantiate the validator
        
        # Compile patterns for efficiency (for searching within text)
        self.compiled_patterns = {
            p: re.compile(pattern, re.IGNORECASE) 
            for p, pattern in self.protocol_regex_patterns_map.items()
        }
        
        # Get the combined regex for splitting from centralized definitions
        self.combined_protocol_regex = get_combined_protocol_regex()

    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        Extracts direct protocol links from any given text.
        This function now uses ConfigValidator.split_configs_from_text
        to first break down the text into valid config-like strings.
        """
        found_links: List[Dict] = []
        
        # Use the validator's split method to get potential clean config strings
        config_candidates = self.config_validator.split_configs_from_text(text_content, self.combined_protocol_regex)

        for candidate in config_candidates:
            # Try to match each candidate against specific protocol patterns
            for protocol_name, compiled_pattern in self.compiled_patterns.items():
                # Use match() to check if the candidate starts with the pattern (and is a full match from start)
                if compiled_pattern.match(candidate): 
                    # Validate the extracted config more deeply using the validator
                    # Pass the protocol name (e.g., 'vmess') not the full 'vmess://'
                    if self.config_validator.validate_protocol_config(candidate, protocol_name):
                        found_links.append({'protocol': protocol_name, 'link': candidate})
                        break # Move to the next candidate once a valid match is found for this chunk
        
        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """Attempts to decode base64 content using ConfigValidator's method."""
        if not settings.ENABLE_BASE64_DECODING:
            return None
        
        decoded_str = self.config_validator.decode_base64_text(content)
        if decoded_str:
            # Check if decoded content looks like a list of links or another parsable format
            if len(decoded_str) > 10 and (self.combined_protocol_regex.search(decoded_str) or 
                                          self.config_validator.is_valid_protocol_prefix(decoded_str)):
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
                            # Reconstruct a shadowssocks link
                            method_pass = f"{proxy_obj['cipher']}:{proxy_obj['password']}"
                            encoded_method_pass = base64.b64encode(method_pass.encode()).decode()
                            ss_link = f"ss://{encoded_method_pass}@{proxy_obj['server']}:{proxy_obj['port']}"
                            if 'name' in proxy_obj:
                                ss_link += f"#{proxy_obj['name']}"
                            
                            if self.config_validator.validate_protocol_config(ss_link, 'ss'): # Pass 'ss' not 'ss://'
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
            pass # Not a valid YAML (Clash) config
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
