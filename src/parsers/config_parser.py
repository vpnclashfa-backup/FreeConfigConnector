# src/parsers/config_parser.py

import base64
import json
import re
import yaml # نیاز به نصب: pip install PyYAML
from src.utils.settings_manager import settings
# RegEx patterns will be imported from telegram_collector as they are generic for protocols
from src.collectors.telegram_collector import get_config_regex_patterns

class ConfigParser:
    def __init__(self):
        self.protocol_regex_patterns = get_config_regex_patterns()

    def _extract_direct_links(self, text_content):
        """
        Extracts direct protocol links (ss://, vmess:// etc.) from any given text.
        """
        found_links = []
        for protocol, pattern in self.protocol_regex_patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for link in matches:
                found_links.append({'protocol': protocol, 'link': link.strip()})
        return found_links

    def _decode_base64(self, content):
        """Attempts to decode base64 content."""
        if not settings.ENABLE_BASE64_DECODING:
            return None
        try:
            # Base64 content is usually plain text or a list of links
            decoded_bytes = base64.b64decode(content, validate=True)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
            print("Successfully decoded Base64 content.")
            return decoded_str
        except Exception:
            # print(f"Not a valid Base64 string or decoding failed: {e}")
            return None

    def _parse_clash_config(self, content):
        """
        Parses Clash YAML configurations to extract proxy links.
        Looks for 'proxies' and 'proxy-providers' sections.
        """
        if not settings.ENABLE_CLASH_PARSER:
            return []

        extracted_links = []
        try:
            clash_data = yaml.safe_load(content)
            if not isinstance(clash_data, dict):
                return [] # Not a valid YAML dictionary

            # Extract from 'proxies' list
            proxies = clash_data.get('proxies', [])
            for proxy_obj in proxies:
                if isinstance(proxy_obj, dict) and 'type' in proxy_obj:
                    # Reconstruct basic link from Clash proxy object
                    proxy_type = proxy_obj['type'].lower()
                    # This is a simplification; a full parser would need to handle all types and their parameters
                    # For now, we try to construct a simple URL-like string or look for standard protocols
                    if proxy_type == 'ss' and 'cipher' in proxy_obj and 'password' in proxy_obj and 'server' in proxy_obj and 'port' in proxy_obj:
                        extracted_links.extend(self._extract_direct_links(f"ss://{proxy_obj['cipher']}:{proxy_obj['password']}@{proxy_obj['server']}:{proxy_obj['port']}"))
                    elif proxy_type == 'vmess' and 'uuid' in proxy_obj and 'server' in proxy_obj and 'port' in proxy_obj:
                        # Vmess in Clash is usually a dict, converting to vmess:// link needs base64 encoding
                        # This is complex, for simplicity, we'll look for direct vmess:// links in the raw content too.
                        pass # We will rely on direct link extraction for this.

            # Extract from 'proxy-providers' (URLs pointing to subscriptions)
            proxy_providers = clash_data.get('proxy-providers', {})
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
                    extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})

            print("Successfully parsed Clash config.")
        except yaml.YAMLError as e:
            # print(f"Not a valid YAML (Clash) config: {e}")
            pass # Not a YAML file or invalid YAML
        except Exception as e:
            print(f"Error parsing Clash config: {e}")
        return extracted_links

    def _parse_singbox_config(self, content):
        """
        Parses SingBox JSON configurations to extract proxy links/outbounds.
        Looks for 'outbounds' section.
        """
        if not settings.ENABLE_SINGBOX_PARSER:
            return []

        extracted_links = []
        try:
            singbox_data = json.loads(content)
            if not isinstance(singbox_data, dict):
                return [] # Not a valid JSON dictionary

            outbounds = singbox_data.get('outbounds', [])
            for outbound_obj in outbounds:
                if isinstance(outbound_obj, dict) and 'type' in outbound_obj:
                    outbound_type = outbound_obj['type'].lower()
                    # Similar to Clash, reconstructing direct links needs specific logic for each type
                    # For SingBox, vmess, vless, trojan outbounds are common
                    if outbound_type == 'vmess' or outbound_type == 'vless' or outbound_type == 'trojan':
                        # SingBox might have its own URL format, or we look for general links
                        # For simplicity, we just check for direct links in the JSON string itself
                        extracted_links.extend(self._extract_direct_links(json.dumps(outbound_obj)))

            print("Successfully parsed SingBox config.")
        except json.JSONDecodeError as e:
            # print(f"Not a valid JSON (SingBox) config: {e}")
            pass # Not a JSON file or invalid JSON
        except Exception as e:
            print(f"Error parsing SingBox config: {e}")
        return extracted_links

    def _parse_json_content(self, content):
        """
        Parses general JSON content to find any embedded config links or subscription URLs.
        """
        if not settings.ENABLE_JSON_PARSER:
            return []

        extracted_links = []
        try:
            json_data = json.loads(content)
            # Recursively search for strings that look like config links or URLs
            json_string = json.dumps(json_data) # Convert entire JSON to a single string for regex search
            extracted_links.extend(self._extract_direct_links(json_string))
            print("Successfully parsed general JSON content.")
        except json.JSONDecodeError:
            pass # Not a valid JSON
        except Exception as e:
            print(f"Error parsing general JSON content: {e}")
        return extracted_links


    def parse_content(self, content):
        """
        Attempts to parse the given content and extract config links using various methods.
        Returns a list of {'protocol': '...', 'link': '...'} dictionaries.
        """
        all_extracted_links = []

        # 1. Try to extract direct links first (always attempt)
        direct_links = self._extract_direct_links(content)
        all_extracted_links.extend(direct_links)

        # 2. Try Base64 decoding
        decoded_content = self._decode_base64(content)
        if decoded_content:
            # After decoding, try to extract direct links again from the decoded content
            base64_links = self._extract_direct_links(decoded_content)
            all_extracted_links.extend(base64_links)

            # Also, try to parse decoded content as Clash/SingBox/JSON
            all_extracted_links.extend(self._parse_clash_config(decoded_content))
            all_extracted_links.extend(self._parse_singbox_config(decoded_content))
            all_extracted_links.extend(self._parse_json_content(decoded_content))


        # 3. Try Clash (YAML) parsing
        clash_links = self._parse_clash_config(content)
        all_extracted_links.extend(clash_links)

        # 4. Try SingBox (JSON) parsing
        singbox_links = self._parse_singbox_config(content)
        all_extracted_links.extend(singbox_links)

        # 5. Try general JSON parsing
        json_links = self._parse_json_content(content)
        all_extracted_links.extend(json_links)

        # Deduplicate extracted links before returning
        return list({link['link']: link for link in all_extracted_links}.values())
