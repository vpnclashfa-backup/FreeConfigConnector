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
        # NEW: ConfigValidator now handles protocol-specific logic
        self.config_validator = ConfigValidator()

        # NEW: Get active protocol information from protocol_definitions
        self.active_protocol_info = get_active_protocol_info()
        self.combined_protocol_prefix_regex = get_combined_protocol_prefix_regex()
        
        # We still need the ordered protocols for matching priority
        self.ordered_protocols_for_matching = ORDERED_PROTOCOLS_FOR_MATCHING

        print("ConfigParser: Initialized with new modular validation system.")


    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        لینک‌های پروتکل مستقیم را از هر محتوای متنی استخراج می‌کند.
        این تابع اکنون از ConfigValidator.split_configs_from_text
        برای تقسیم متن به رشته‌های کانفیگ‌مانند معتبر استفاده می‌کند.
        """
        found_links: List[Dict] = []
        print(f"ConfigParser: Extracting direct links from text content (length: {len(text_content)}).") # Detailed log

        # از متد تقسیم‌بندی اعتبارسنج برای به دست آوردن قطعات کانفیگ تمیز احتمالی استفاده کن
        # config_validator خودش پاکسازی اولیه (trailing junk) را انجام می‌دهد
        config_candidates = self.config_validator.split_configs_from_text(text_content)
        print(f"ConfigParser: Split text into {len(config_candidates)} config candidates.") # Detailed log


        for candidate in config_candidates:
            # از طریق پروتکل‌های مرتب شده برای تطبیق اولویت‌دار تکرار کن (خاص‌ترها اول)
            matched_protocol = None
            for protocol_name in self.ordered_protocols_for_matching:
                protocol_info = self.active_protocol_info.get(protocol_name)
                
                if protocol_info and isinstance(protocol_info["prefix"], str):
                    # Check if the candidate starts with the prefix for this protocol
                    if candidate.startswith(protocol_info["prefix"]):
                        # NEW: Use the centralized cleaning and validation from ConfigValidator
                        cleaned_candidate = self.config_validator.clean_protocol_config(candidate, protocol_name)
                        
                        is_valid = self.config_validator.validate_protocol_config(cleaned_candidate, protocol_name)
                        
                        if is_valid:
                            found_links.append({'protocol': protocol_name, 'link': cleaned_candidate})
                            print(f"ConfigParser: VALID link found for {protocol_name}: {cleaned_candidate[:100]}...") # Success log
                            matched_protocol = protocol_name # Mark as matched
                            break # Move to next candidate once a protocol is found and processed for it
                        
                        # Special handling for "reality" which is a VLESS variant
                        elif protocol_name == "vless":
                            # Check if it's a Reality link using the VLESS validator if it's available
                            vless_validator = self.config_validator.protocol_validators.get("vless")
                            if vless_validator and hasattr(vless_validator, 'is_reality_link') and vless_validator.is_reality_link(cleaned_candidate):
                                found_links.append({'protocol': 'reality', 'link': cleaned_candidate})
                                print(f"ConfigParser: VALID Reality link found (VLESS variant): {cleaned_candidate[:100]}...") # Success log
                                matched_protocol = 'reality' # Mark as matched
                                break
                    # else:
                        # print(f"ConfigParser: Candidate '{candidate[:50]}...' does not start with protocol prefix '{protocol_info['prefix']}'.") # Too verbose
                # else:
                    # print(f"ConfigParser: Protocol info not found or prefix invalid for '{protocol_name}'.") # Too verbose

            if not matched_protocol and candidate:
                print(f"ConfigParser: Candidate '{candidate[:100]}...' did NOT match any active protocol or failed validation.") # Failed match log

        print(f"ConfigParser: Finished direct link extraction. Found {len(found_links)} links.") # Summary log
        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """تلاش می‌کند محتوای base64 را با استفاده از متد ConfigValidator رمزگشایی کند."""
        if not settings.ENABLE_BASE64_DECODING:
            print("ConfigParser: Base64 decoding is disabled in settings.") # Log if disabled
            return None

        print(f"ConfigParser: Attempting to decode Base64 content (length: {len(content)}).") # Detailed log
        decoded_str = self.config_validator.decode_base64_text(content)
        if decoded_str:
            # بررسی کن آیا محتوای رمزگشایی شده شبیه لیستی از لینک‌ها یا فرمت قابل پارس دیگری است
            if len(decoded_str) > 10 and (self.combined_protocol_prefix_regex.search(decoded_str) or 
                                          self.config_validator.is_valid_protocol_prefix(decoded_str)):
                print("ConfigParser: Base64 content successfully decoded and contains potential links. Proceeding with parsing decoded content.") # Success log
                return decoded_str
            print("ConfigParser: Base64 decoded, but content does not seem to contain valid configs or protocol links.") # Log if decoded but not valid looking
            return None
        print("ConfigParser: Failed to decode content as Base64.") # Log if decoding failed
        return None

    def _parse_clash_config(self, content: str) -> List[Dict]:
        """
        پیکربندی‌های Clash YAML را برای استخراج لینک‌های پروکسی پارس می‌کند.
        """
        if not settings.ENABLE_CLASH_PARSER:
            print("ConfigParser: Clash parser is disabled in settings.") # Log if disabled
            return []

        extracted_links: List[Dict] = []
        print(f"ConfigParser: Attempting to parse Clash config (content length: {len(content)}).") # Detailed log
        try:
            clash_data = yaml.safe_load(content)
            if not isinstance(clash_data, dict):
                print("ConfigParser: Clash content is not a valid YAML dictionary. Skipping.") # Invalid YAML
                return []

            # استخراج از لیست 'proxies'
            proxies = clash_data.get('proxies', [])
            print(f"ConfigParser: Found {len(proxies)} proxies in Clash config.") # Detailed log
            for proxy_obj in proxies:
                if isinstance(proxy_obj, dict):
                    # تلاش برای بازسازی لینک‌های SS/SSR از دیکشنری، سپس اعتبارسنجی
                    if proxy_obj.get('type', '').lower() == 'ss' and all(k in proxy_obj for k in ['cipher', 'password', 'server', 'port']):
                        try:
                            method_pass = f"{proxy_obj['cipher']}:{proxy_obj['password']}"
                            encoded_method_pass = base64.urlsafe_b64encode(method_pass.encode()).decode().rstrip('=')
                            ss_link = f"ss://{encoded_method_pass}@{proxy_obj['server']}:{proxy_obj['port']}"
                            if 'name' in proxy_obj:
                                from urllib.parse import quote
                                ss_link += f"#{quote(proxy_obj['name'])}"

                            cleaned_ss_link = self.config_validator.clean_protocol_config(ss_link, 'ss')
                            if self.config_validator.validate_protocol_config(cleaned_ss_link, 'ss'):
                                extracted_links.append({'protocol': 'ss', 'link': cleaned_ss_link})
                                print(f"ConfigParser: Successfully reconstructed and validated SS link from Clash proxy: {cleaned_ss_link[:100]}...") # Success
                            else:
                                print(f"ConfigParser: Reconstructed SS link from Clash proxy failed validation: {cleaned_ss_link[:100]}...") # Failed validation
                        except Exception as e:
                            print(f"ConfigParser: ERROR reconstructing/validating SS link from Clash: {e}. Proxy obj: {proxy_obj}") # Error
                    
                    # برای انواع دیگر (vmess, vless, trojan)، آن‌ها اغلب لینک‌های مستقیم یا پیچیده هستند.
                    # ما برای یافتن لینک‌های پروتکل مستقیم به جستجو در نمایش رشته JSON تکیه می‌کنیم.
                    proxy_str_representation = json.dumps(proxy_obj)
                    direct_links_from_proxy = self._extract_direct_links(proxy_str_representation)
                    extracted_links.extend(direct_links_from_proxy)
                    if direct_links_from_proxy:
                        print(f"ConfigParser: Extracted {len(direct_links_from_proxy)} direct links from Clash proxy object.") # Extracted from proxy object


            # استخراج از 'proxy-providers' (URLهایی که به اشتراک‌ها اشاره می‌کنند)
            proxy_providers = clash_data.get('proxy-providers', {})
            print(f"ConfigParser: Found {len(proxy_providers)} proxy providers in Clash config.") # Detailed log
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
                    if provider_obj['url'].startswith('http://') or provider_obj['url'].startswith('https://'):
                        extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})
                        print(f"ConfigParser: Found Clash subscription URL: {provider_obj['url']}. Added for discovery.") # Subscription URL

            print(f"ConfigParser: Clash config parsed successfully. Total links extracted: {len(extracted_links)}.")
        except yaml.YAMLError as e:
            print(f"ConfigParser: ERROR: Invalid YAML format for Clash config: {e}") # Specific YAML error
        except Exception as e:
            print(f"ConfigParser: ERROR parsing Clash configuration: {e}") # General error
            traceback.print_exc() # Print full traceback
        return extracted_links

    def _parse_singbox_config(self, content: str) -> List[Dict]:
        """
        پیکربندی‌های SingBox JSON را برای استخراج لینک‌های پروکسی/outbounds پارس می‌کند.
        """
        if not settings.ENABLE_SINGBOX_PARSER:
            print("ConfigParser: SingBox parser is disabled in settings.") # Log if disabled
            return []

        extracted_links: List[Dict] = []
        print(f"ConfigParser: Attempting to parse SingBox config (content length: {len(content)}).") # Detailed log
        try:
            singbox_data = json.loads(content)
            if not isinstance(singbox_data, dict):
                print("ConfigParser: SingBox content is not a valid JSON dictionary. Skipping.") # Invalid JSON
                return []

            outbounds = singbox_data.get('outbounds', [])
            print(f"ConfigParser: Found {len(outbounds)} outbounds in SingBox config.") # Detailed log
            for outbound_obj in outbounds:
                if isinstance(outbound_obj, dict):
                    # Check for 'type' and 'tag' to ensure it's a proxy outbound
                    if 'type' in outbound_obj and outbound_obj['type'] != 'direct' and outbound_obj['type'] != 'block':
                        outbound_str = json.dumps(outbound_obj)
                        direct_links_from_outbound = self._extract_direct_links(outbound_str)
                        extracted_links.extend(direct_links_from_outbound)
                        if direct_links_from_outbound:
                            print(f"ConfigParser: Extracted {len(direct_links_from_outbound)} direct links from SingBox outbound object.") # Extracted from outbound object

            print(f"ConfigParser: SingBox config parsed successfully. Total links extracted: {len(extracted_links)}.")
        except json.JSONDecodeError as e:
            print(f"ConfigParser: ERROR: Invalid JSON format for SingBox config: {e}") # Specific JSON error
        except Exception as e:
            print(f"ConfigParser: ERROR parsing SingBox configuration: {e}") # General error
            traceback.print_exc() # Print full traceback
        return extracted_links

    def _parse_json_content(self, content: str) -> List[Dict]:
        """
        محتوای JSON عمومی را برای یافتن هر لینک کانفیگ جاسازی شده یا URL اشتراک پارس می‌کند.
        """
        if not settings.ENABLE_JSON_PARSER:
            print("ConfigParser: Generic JSON parser is disabled in settings.") # Log if disabled
            return []

        extracted_links: List[Dict] = []
        print(f"ConfigParser: Attempting to parse generic JSON content (content length: {len(content)}).") # Detailed log
        try:
            json_data = json.loads(content)
            json_string = json.dumps(json_data)
            direct_links_from_json = self._extract_direct_links(json_string)
            extracted_links.extend(direct_links_from_json)
            if direct_links_from_json:
                print(f"ConfigParser: Extracted {len(direct_links_from_json)} direct links from generic JSON content.") # Extracted from JSON

            print(f"ConfigParser: Generic JSON content parsed successfully. Total links extracted: {len(extracted_links)}.")
        except json.JSONDecodeError as e:
            print(f"ConfigParser: ERROR: Invalid JSON format for generic JSON content: {e}") # Specific JSON error
        except Exception as e:
            print(f"ConfigParser: ERROR parsing generic JSON content: {e}") # General error
            traceback.print_exc() # Print full traceback
        return extracted_links


    def parse_content(self, content: str) -> List[Dict]:
        """
        تلاش می‌کند محتوای داده شده را پارس کرده و لینک‌های کانفیگ را با استفاده از روش‌های مختلف استخراج کند.
        لیستی از دیکشنری‌های {'protocol': '...', 'link': '...'} را برمی‌گرداند.
        """
        all_extracted_links: List[Dict] = []
        print(f"\nConfigParser: Starting content parsing process for input of length {len(content)}.") # Start of major parsing

        # ۱. ابتدا لینک‌های مستقیم را از محتوای خام استخراج کن
        print("ConfigParser: Attempting to extract direct links from raw content.")
        direct_links = self._extract_direct_links(content)
        all_extracted_links.extend(direct_links)
        print(f"ConfigParser: Found {len(direct_links)} direct links from raw content.")

        # ۲. رمزگشایی Base64 و سپس پارس کردن محتوای رمزگشایی شده
        print("ConfigParser: Attempting Base64 decoding and subsequent parsing.")
        decoded_content = self._decode_base64(content)
        if decoded_content:
            print("ConfigParser: Successfully decoded Base64. Now parsing decoded content.")
            base64_links = self._extract_direct_links(decoded_content)
            all_extracted_links.extend(base64_links)
            print(f"ConfigParser: Found {len(base64_links)} links from decoded Base64 content directly.")

            # سپس، تلاش کن محتوای رمزگشایی شده را به عنوان Clash/SingBox/JSON عمومی پارس کنی
            all_extracted_links.extend(self._parse_clash_config(decoded_content))
            all_extracted_links.extend(self._parse_singbox_config(decoded_content))
            all_extracted_links.extend(self._parse_json_content(decoded_content))
        else:
            print("ConfigParser: Base64 decoding failed or resulted in no relevant content.")


        # ۳. پارس کردن Clash (YAML) از محتوای خام
        print("ConfigParser: Attempting to parse Clash config from raw content.")
        clash_links = self._parse_clash_config(content)
        all_extracted_links.extend(clash_links)
        print(f"ConfigParser: Found {len(clash_links)} links from raw Clash parsing.")

        # ۴. پارس کردن SingBox (JSON) از محتوای خام
        print("ConfigParser: Attempting to parse SingBox config from raw content.")
        singbox_links = self._parse_singbox_config(content)
        all_extracted_links.extend(singbox_links)
        print(f"ConfigParser: Found {len(singbox_links)} links from raw SingBox parsing.")

        # ۵. پارس کردن JSON عمومی از محتوای خام
        print("ConfigParser: Attempting to parse generic JSON from raw content.")
        json_links = self._parse_json_content(content)
        all_extracted_links.extend(json_links)
        print(f"ConfigParser: Found {len(json_links)} links from raw generic JSON parsing.")

        # حذف لینک‌های تکراری قبل از بازگشت
        unique_links = list({link['link']: link for link in all_extracted_links}.values())
        print(f"ConfigParser: Finished content parsing. Total unique links after all methods: {len(unique_links)}") # Final summary
        return unique_links