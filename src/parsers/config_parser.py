# src/parsers/config_parser.py

import base64
import json
import re
import yaml # pip install PyYAML
from typing import List, Dict, Optional, Tuple
from urllib.parse import unquote, urlparse # Only if still needed directly here

# Import from centralized protocol definitions and ConfigValidator
from src.utils.protocol_definitions import get_protocol_regex_patterns, get_combined_protocol_regex
from src.utils.config_validator import ConfigValidator 

# Re-using settings directly from utils
from src.utils.settings_manager import settings


class ConfigParser:
    def __init__(self):
        self.protocol_regex_patterns_map = get_protocol_regex_patterns()
        self.config_validator = ConfigValidator()
        
        # Compile patterns for efficiency (for searching within text)
        self.compiled_patterns = {
            p: re.compile(pattern, re.IGNORECASE) 
            for p, pattern in self.protocol_regex_patterns_map.items()
        }
        
        self.combined_protocol_regex = get_combined_protocol_regex()

        # NEW: Ordered list of protocol names for prioritized matching.
        # Reality should be checked before generic VLESS.
        self.ordered_protocols_for_matching = [
            "reality", # Check Reality first as it's a VLESS variant
            "vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2",
            "tuic", "wireguard", "ssh", "warp", "juicity", "http", "https", "socks5",
            "mieru", "snell", "anytls"
            # Ensure this list covers all active_protocols from settings
            # Order is important for accurate classification (more specific first)
        ]


    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        Extracts direct protocol links from any given text.
        This function uses ConfigValidator.split_configs_from_text
        to first break down the text into valid config-like strings.
        """
        found_links: List[Dict] = []
        
        config_candidates = self.config_validator.split_configs_from_text(text_content, self.combined_protocol_regex)

        for candidate in config_candidates:
            # NEW: Iterate through ordered protocols for prioritized matching
            for protocol_name in self.ordered_protocols_for_matching:
                # Check if the candidate matches the pattern for this protocol AND is active
                if protocol_name in self.protocol_regex_patterns_map:
                    compiled_pattern = self.compiled_patterns[protocol_name]
                    if compiled_pattern.match(candidate):
                        # Validate the extracted config with the validator's specific protocol validation
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

            proxies = clash_data.get('proxies', [])
            for proxy_obj in proxies:
                if isinstance(proxy_obj, dict):
                    if proxy_obj.get('type', '').lower() == 'ss' and all(k in proxy_obj for k in ['cipher', 'password', 'server', 'port']):
                        try:
                            method_pass = f"{proxy_obj['cipher']}:{proxy_obj['password']}"
                            encoded_method_pass = base64.b64encode(method_pass.encode()).decode()
                            ss_link = f"ss://{encoded_method_pass}@{proxy_obj['server']}:{proxy_obj['port']}"
                            if 'name' in proxy_obj:
                                ss_link += f"#{proxy_obj['name']}"
                            
                            if self.config_validator.validate_protocol_config(ss_link, 'ss'):
                                extracted_links.append({'protocol': 'ss', 'link': ss_link})
                        except Exception as e:
                            print(f"Error reconstructing SS link from Clash: {e}")
                    
                    proxy_str_representation = json.dumps(proxy_obj)
                    extracted_links.extend(self._extract_direct_links(proxy_str_representation))


            proxy_providers = clash_data.get('proxy-providers', {})
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
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
        
        direct_links = self._extract_direct_links(content)
        all_extracted_links.extend(direct_links)
        
        decoded_content = self._decode_base64(content)
        if decoded_content:
            base64_links = self._extract_direct_links(decoded_content)
            all_extracted_links.extend(base64_links)
            
            all_extracted_links.extend(self._parse_clash_config(decoded_content))
            all_extracted_links.extend(self._parse_singbox_config(decoded_content))
            all_extracted_links.extend(self._parse_json_content(decoded_content))


        clash_links = self._parse_clash_config(content)
        all_extracted_links.extend(clash_links)

        singbox_links = self._parse_singbox_config(content)
        all_extracted_links.extend(singbox_links)

        json_links = self._parse_json_content(content)
        all_extracted_links.extend(json_links)
        
        return list({link['link']: link for link in all_extracted_links}.values())
