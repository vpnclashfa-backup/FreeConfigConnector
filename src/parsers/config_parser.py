import base64
import json
import re
import yaml # pip install PyYAML
from typing import List, Dict, Optional, Tuple, Union # Ensure Union is imported

# وارد کردن تعاریف پروتکل مرکزی و ConfigValidator
from src.utils.protocol_definitions import get_active_protocol_info, get_combined_protocol_prefix_regex, ORDERED_PROTOCOLS_FOR_MATCHING
from src.utils.config_validator import ConfigValidator

# استفاده مستقیم از تنظیمات از utils
from src.utils.settings_manager import settings


class ConfigParser:
    def __init__(self):
        self.config_validator = ConfigValidator()
        self.active_protocol_info = get_active_protocol_info()
        self.combined_protocol_prefix_regex = get_combined_protocol_prefix_regex()
        self.ordered_protocols_for_matching = ORDERED_PROTOCOLS_FOR_MATCHING

        print("ConfigParser: Initialized with new modular validation system.")


    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        لینک‌های پروتکل مستقیم را از هر محتوای متنی استخراج می‌کند.
        این تابع اکنون از ConfigValidator.split_configs_from_text
        برای تقسیم متن به رشته‌های کانفیگ‌مانند معتبر استفاده می‌کند.
        """
        found_links: List[Dict] = []
        print(f"ConfigParser: Extracting direct links from text content (length: {len(text_content)}).")

        config_candidates = self.config_validator.split_configs_from_text(text_content)
        print(f"ConfigParser: Split text into {len(config_candidates)} raw config candidates.")


        for candidate in config_candidates:
            # Try to match Reality first if it's a VLESS candidate
            is_reality_candidate = False
            if candidate.startswith("vless://"):
                vless_validator_class = self.config_validator.protocol_validators.get("vless")
                if vless_validator_class and hasattr(vless_validator_class, 'is_reality_link') and vless_validator_class.is_reality_link(candidate):
                    is_reality_candidate = True
                    print(f"ConfigParser: Candidate '{candidate[:100]}...' identified as a potential Reality link (VLESS variant).")
                    
                    # Clean and validate Reality (as 'reality' protocol)
                    cleaned_candidate = self.config_validator.clean_protocol_config(candidate, 'reality') # Clean as reality
                    if self.config_validator.validate_protocol_config(cleaned_candidate, 'reality'): # Validate as reality
                        found_links.append({'protocol': 'reality', 'link': cleaned_candidate})
                        print(f"ConfigParser: VALID Reality link found: {cleaned_candidate[:100]}...")
                        continue # Move to next candidate, as Reality is a VLESS variant, we don't need to re-check as VLESS

            # If not a Reality candidate, or Reality validation failed, proceed with ordered protocol matching
            # Note: We iterate through all ordered_protocols_for_matching to cover all cases without premature break.
            matched_protocol_for_candidate = False
            for protocol_name in self.ordered_protocols_for_matching:
                if protocol_name == "reality": # Skip "reality" itself as it's a VLESS variant handled above
                    continue

                protocol_info = self.active_protocol_info.get(protocol_name)
                
                if protocol_info and isinstance(protocol_info["prefix"], str):
                    if candidate.startswith(protocol_info["prefix"]):
                        # NEW: Use the centralized cleaning and validation from ConfigValidator
                        cleaned_candidate = self.config_validator.clean_protocol_config(candidate, protocol_name)
                        
                        is_valid = self.config_validator.validate_protocol_config(cleaned_candidate, protocol_name)
                        
                        if is_valid:
                            found_links.append({'protocol': protocol_name, 'link': cleaned_candidate})
                            print(f"ConfigParser: VALID link found for {protocol_name}: {cleaned_candidate[:100]}...")
                            matched_protocol_for_candidate = True
                            break # Found a valid match, move to next candidate
                        else:
                            print(f"ConfigParser: Candidate '{cleaned_candidate[:100]}...' for protocol '{protocol_name}' failed specific validation.")
                # else:
                    # print(f"ConfigParser: Protocol info not found or prefix invalid for '{protocol_name}'.")

            if not is_reality_candidate and not matched_protocol_for_candidate and candidate:
                print(f"ConfigParser: Candidate '{candidate[:100]}...' did NOT match any active protocol or failed validation after all checks.")

        print(f"ConfigParser: Finished direct link extraction. Found {len(found_links)} links.")
        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """تلاش می‌کند محتوای base64 را با استفاده از متد ConfigValidator رمزگشایی کند."""
        if not settings.ENABLE_BASE64_DECODING:
            print("ConfigParser: Base64 decoding is disabled in settings.")
            return None

        print(f"ConfigParser: Attempting to decode Base64 content (length: {len(content)}).")
        decoded_str = self.config_validator.decode_base64_text(content)
        if decoded_str:
            # بررسی کن آیا محتوای رمزگشایی شده شبیه لیستی از لینک‌ها یا فرمت قابل پارس دیگری است
            if len(decoded_str) > 10 and (self.combined_protocol_prefix_regex.search(decoded_str) or 
                                          self.config_validator.is_valid_protocol_prefix(decoded_str)):
                print("ConfigParser: Base64 content successfully decoded and contains potential links. Proceeding with parsing decoded content.")
                return decoded_str
            print("ConfigParser: Base64 decoded, but content does not seem to contain valid configs or protocol links.")
            return None
        print("ConfigParser: Failed to decode content as Base64.")
        return None

    def _parse_clash_config(self, content: str) -> List[Dict]:
        """
        پیکربندی‌های Clash YAML را برای استخراج لینک‌های پروکسی پارس می‌کند.
        """
        if not settings.ENABLE_CLASH_PARSER:
            print("ConfigParser: Clash parser is disabled in settings.")
            return []

        extracted_links: List[Dict] = []
        print(f"ConfigParser: Attempting to parse Clash config (content length: {len(content)}).")
        try:
            clash_data = yaml.safe_load(content)
            if not isinstance(clash_data, dict):
                print(f"ConfigParser: Clash content is not a valid YAML dictionary. Skipping. Content starts with: '{content[:50]}...'")
                return []

            # استخراج از لیست 'proxies'
            proxies = clash_data.get('proxies', [])
            print(f"ConfigParser: Found {len(proxies)} proxies in Clash config.")
            for proxy_obj in proxies:
                if isinstance(proxy_obj, dict):
                    # Attempt to reconstruct SS/SSR links from dictionary properties
                    if proxy_obj.get('type', '').lower() == 'ss' and all(k in proxy_obj for k in ['cipher', 'password', 'server', 'port']):
                        try:
                            method_pass = f"{proxy_obj['cipher']}:{proxy_obj['password']}"
                            encoded_method_pass = base64.urlsafe_b64encode(method_pass.encode()).decode().rstrip('=')
                            ss_link = f"ss://{encoded_method_pass}@{proxy_obj['server']}:{proxy_obj['port']}"
                            if 'name' in proxy_obj:
                                from urllib.parse import quote
                                ss_link += f"#{quote(str(proxy_obj['name']))}" # Ensure name is string and URL-encoded

                            cleaned_ss_link = self.config_validator.clean_protocol_config(ss_link, 'ss')
                            if self.config_validator.validate_protocol_config(cleaned_ss_link, 'ss'):
                                extracted_links.append({'protocol': 'ss', 'link': cleaned_ss_link})
                                print(f"ConfigParser: Successfully reconstructed and validated SS link from Clash proxy: {cleaned_ss_link[:100]}...")
                            else:
                                print(f"ConfigParser: Reconstructed SS link from Clash proxy failed validation: {cleaned_ss_link[:100]}...")
                        except Exception as e:
                            print(f"ConfigParser: ERROR reconstructing/validating SS link from Clash: {e}. Proxy obj: {proxy_obj}")
                    
                    elif proxy_obj.get('type', '').lower() == 'ssr' and all(k in proxy_obj for k in ['server', 'port', 'protocol', 'method', 'obfs', 'password']):
                        try:
                            # Reconstruct SSR link (simplified example, real SSR links are complex)
                            # This needs to match the structure expected by SsrValidator
                            ssr_part = f"{proxy_obj['server']}:{proxy_obj['port']}:{proxy_obj['protocol']}:{proxy_obj['method']}:{proxy_obj['obfs']}:{proxy_obj['password']}"
                            # Handle optional params like obfsparam, protparam
                            optional_params = []
                            if 'obfsparam' in proxy_obj: optional_params.append(f"obfsparam={base64.urlsafe_b64encode(str(proxy_obj['obfsparam']).encode()).decode().rstrip('=')}")
                            if 'protparam' in proxy_obj: optional_params.append(f"protparam={base64.urlsafe_b64encode(str(proxy_obj['protparam']).encode()).decode().rstrip('=')}")
                            
                            ssr_full_encoded = base64.urlsafe_b64encode(ssr_part.encode()).decode().rstrip('=')
                            ssr_link = f"ssr://{ssr_full_encoded}"
                            if optional_params:
                                ssr_link += f"/?{'&'.join(optional_params)}"
                            if 'name' in proxy_obj:
                                from urllib.parse import quote
                                ssr_link += f"#{quote(str(proxy_obj['name']))}"

                            cleaned_ssr_link = self.config_validator.clean_protocol_config(ssr_link, 'ssr')
                            if self.config_validator.validate_protocol_config(cleaned_ssr_link, 'ssr'):
                                extracted_links.append({'protocol': 'ssr', 'link': cleaned_ssr_link})
                                print(f"ConfigParser: Successfully reconstructed and validated SSR link from Clash proxy: {cleaned_ssr_link[:100]}...")
                            else:
                                print(f"ConfigParser: Reconstructed SSR link from Clash proxy failed validation: {cleaned_ssr_link[:100]}...")
                        except Exception as e:
                            print(f"ConfigParser: ERROR reconstructing/validating SSR link from Clash: {e}. Proxy obj: {proxy_obj}")

                    # For other types (vmess, vless, trojan), they often have direct links embedded in string form.
                    # We search in their JSON string representation.
                    proxy_str_representation = json.dumps(proxy_obj)
                    direct_links_from_proxy = self._extract_direct_links(proxy_str_representation)
                    extracted_links.extend(direct_links_from_proxy)
                    if direct_links_from_proxy:
                        print(f"ConfigParser: Extracted {len(direct_links_from_proxy)} direct links from Clash proxy object's string representation.")


            # استخراج از 'proxy-providers' (URLهایی که به اشتراک‌ها اشاره می‌کنند)
            proxy_providers = clash_data.get('proxy-providers', {})
            print(f"ConfigParser: Found {len(proxy_providers)} proxy providers in Clash config.")
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
                    if provider_obj['url'].startswith('http://') or provider_obj['url'].startswith('https://'):
                        extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})
                        print(f"ConfigParser: Found Clash subscription URL: {provider_obj['url']}. Added for discovery.")

            print(f"ConfigParser: Clash config parsed successfully. Total links extracted: {len(extracted_links)}.")
        except yaml.YAMLError as e:
            print(f"ConfigParser: ERROR: Invalid YAML format for Clash config: {e}. Content starts with: '{content[:100]}...'")
        except Exception as e:
            print(f"ConfigParser: ERROR parsing Clash configuration: {e}")
            traceback.print_exc()
        return extracted_links

    def _parse_singbox_config(self, content: str) -> List[Dict]:
        """
        پیکربندی‌های SingBox JSON را برای استخراج لینک‌های پروکسی/outbounds پارس می‌کند.
        """
        if not settings.ENABLE_SINGBOX_PARSER:
            print("ConfigParser: SingBox parser is disabled in settings.")
            return []

        extracted_links: List[Dict] = []
        print(f"ConfigParser: Attempting to parse SingBox config (content length: {len(content)}).")
        try:
            singbox_data = json.loads(content)
            if not isinstance(singbox_data, dict):
                print(f"ConfigParser: SingBox content is not a valid JSON dictionary. Skipping. Content starts with: '{content[:50]}...'")
                return []

            outbounds = singbox_data.get('outbounds', [])
            print(f"ConfigParser: Found {len(outbounds)} outbounds in SingBox config.")
            for outbound_obj in outbounds:
                if isinstance(outbound_obj, dict):
                    # Check for 'type' and 'tag' to ensure it's a proxy outbound
                    if 'type' in outbound_obj and outbound_obj['type'] not in ['direct', 'block', 'selector', 'urltest', 'fallback', 'loadbalance', 'dns', 'http', 'socks'] : # Exclude common non-proxy outbound types
                        outbound_str = json.dumps(outbound_obj)
                        direct_links_from_outbound = self._extract_direct_links(outbound_str)
                        extracted_links.extend(direct_links_from_outbound)
                        if direct_links_from_outbound:
                            print(f"ConfigParser: Extracted {len(direct_links_from_outbound)} direct links from SingBox outbound object.")
                    # Also check for subscription links within 'outbound' if SingBox supports it
                    elif outbound_obj.get('type') == 'urltest' and 'url' in outbound_obj and isinstance(outbound_obj['url'], str) and (outbound_obj['url'].startswith('http://') or outbound_obj['url'].startswith('https://')):
                        extracted_links.append({'protocol': 'subscription', 'link': outbound_obj['url']})
                        print(f"ConfigParser: Found SingBox subscription URL in urltest outbound: {outbound_obj['url']}. Added for discovery.")


            print(f"ConfigParser: SingBox config parsed successfully. Total links extracted: {len(extracted_links)}.")
        except json.JSONDecodeError as e:
            print(f"ConfigParser: ERROR: Invalid JSON format for SingBox config: {e}. Content starts with: '{content[:100]}...'")
        except Exception as e:
            print(f"ConfigParser: ERROR parsing SingBox configuration: {e}")
            traceback.print_exc()
        return extracted_links

    def _parse_json_content(self, content: str) -> List[Dict]:
        """
        محتوای JSON عمومی را برای یافتن هر لینک کانفیگ جاسازی شده یا URL اشتراک پارس می‌کند.
        """
        if not settings.ENABLE_JSON_PARSER:
            print("ConfigParser: Generic JSON parser is disabled in settings.")
            return []

        extracted_links: List[Dict] = []
        print(f"ConfigParser: Attempting to parse generic JSON content (content length: {len(content)}).")
        try:
            json_data = json.loads(content)
            json_string = json.dumps(json_data)
            direct_links_from_json = self._extract_direct_links(json_string)
            extracted_links.extend(direct_links_from_json)
            if direct_links_from_json:
                print(f"ConfigParser: Extracted {len(direct_links_from_json)} direct links from generic JSON content.")

            print(f"ConfigParser: Generic JSON content parsed successfully. Total links extracted: {len(extracted_links)}.")
        except json.JSONDecodeError as e:
            print(f"ConfigParser: ERROR: Invalid JSON format for generic JSON content: {e}. Content starts with: '{content[:100]}...'")
        except Exception as e:
            print(f"ConfigParser: ERROR parsing generic JSON content: {e}")
            traceback.print_exc()
        return extracted_links


    def parse_content(self, content: str) -> List[Dict]:
        """
        تلاش می‌کند محتوای داده شده را پارس کرده و لینک‌های کانفیگ را با استفاده از روش‌های مختلف استخراج کند.
        لیستی از دیکشنری‌های {'protocol': '...', 'link': '...'} را برمی‌گرداند.
        """
        all_extracted_links: List[Dict] = []
        print(f"\nConfigParser: Starting content parsing process for input of length {len(content)}.")

        # 1. First, extract direct links from raw content
        print("ConfigParser: Attempting to extract direct links from raw content.")
        direct_links = self._extract_direct_links(content)
        all_extracted_links.extend(direct_links)
        print(f"ConfigParser: Found {len(direct_links)} direct links from raw content.")

        # 2. Decode Base64 and then parse the decoded content
        print("ConfigParser: Attempting Base64 decoding and subsequent parsing.")
        decoded_content = self._decode_base64(content)
        if decoded_content:
            print("ConfigParser: Successfully decoded Base64. Now parsing decoded content.")
            base64_links = self._extract_direct_links(decoded_content)
            all_extracted_links.extend(base64_links)
            print(f"ConfigParser: Found {len(base64_links)} links from decoded Base64 content directly.")

            all_extracted_links.extend(self._parse_clash_config(decoded_content))
            all_extracted_links.extend(self._parse_singbox_config(decoded_content))
            all_extracted_links.extend(self._parse_json_content(decoded_content))
        else:
            print("ConfigParser: Base64 decoding failed or resulted in no relevant content.")


        # 3. Parse Clash (YAML) from raw content (if not already parsed from decoded content)
        # This is important because sometimes the raw content itself is a Clash config, not base64.
        # Only try if we didn't get any links from direct parsing of raw, and decoded content didn't yield Clash links
        print("ConfigParser: Attempting to parse Clash config from raw content.")
        clash_links = self._parse_clash_config(content)
        all_extracted_links.extend(clash_links)
        print(f"ConfigParser: Found {len(clash_links)} links from raw Clash parsing.")

        # 4. Parse SingBox (JSON) from raw content
        print("ConfigParser: Attempting to parse SingBox config from raw content.")
        singbox_links = self._parse_singbox_config(content)
        all_extracted_links.extend(singbox_links)
        print(f"ConfigParser: Found {len(singbox_links)} links from raw SingBox parsing.")

        # 5. Parse generic JSON from raw content
        print("ConfigParser: Attempting to parse generic JSON from raw content.")
        json_links = self._parse_json_content(content)
        all_extracted_links.extend(json_links)
        print(f"ConfigParser: Found {len(json_links)} links from raw generic JSON parsing.")

        # Remove duplicate links before returning
        unique_links = list({link['link']: link for link in all_extracted_links}.values())
        print(f"ConfigParser: Finished content parsing. Total unique links after all methods: {len(unique_links)}")
        return unique_links