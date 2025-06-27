# src/parsers/config_parser.py

import base64
import json
import re
import yaml # نیاز به نصب: pip install PyYAML
from typing import List, Dict, Optional # NEW: Import List, Dict, Optional
from src.utils.settings_manager import settings
from src.collectors.telegram_collector import get_config_regex_patterns # Re-using regex patterns

class ConfigParser:
    def __init__(self):
        self.protocol_regex_patterns = get_config_regex_patterns()

    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        Extracts direct protocol links (ss://, vmess:// etc.) from any given text.
        """
        found_links: List[Dict] = []
        for protocol, pattern in self.protocol_regex_patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for link in matches:
                found_links.append({'protocol': protocol, 'link': link.strip()})
        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """Attempts to decode base64 content."""
        if not settings.ENABLE_BASE64_DECODING:
            return None
        try:
            decoded_bytes = base64.b64decode(content, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
            print("Successfully decoded Base64 content.")
            return decoded_str
        except Exception:
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
                if isinstance(proxy_obj, dict) and 'type' in proxy_obj:
                    proxy_type = proxy_obj['type'].lower()
                    if proxy_type == 'ss' and 'cipher' in proxy_obj and 'password' in proxy_obj and 'server' in proxy_obj and 'port' in proxy_obj:
                        extracted_links.extend(self._extract_direct_links(f"ss://{proxy_obj['cipher']}:{proxy_obj['password']}@{proxy_obj['server']}:{proxy_obj['port']}"))
                    # Note: Full reconstruction of complex types like vmess from Clash YAML is advanced.
                    # We rely on direct link extraction for common protocol URL types here.

            proxy_providers = clash_data.get('proxy-providers', {})
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
                    extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})
            
            print("Successfully parsed Clash config.")
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
                if isinstance(outbound_obj, dict) and 'type' in outbound_obj:
                    outbound_type = outbound_obj['type'].lower()
                    # We look for direct links in the JSON string itself
                    extracted_links.extend(self._extract_direct_links(json.dumps(outbound_obj)))
                        
                print("Successfully parsed SingBox config.")
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
            print("Successfully parsed general JSON content.")
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
