import base64
import json
import re
import yaml # pip install PyYAML
from typing import List, Dict, Optional, Tuple

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

        # از متد تقسیم‌بندی اعتبارسنج برای به دست آوردن قطعات کانفیگ تمیز احتمالی استفاده کن
        # config_validator خودش پاکسازی اولیه (trailing junk) را انجام می‌دهد
        config_candidates = self.config_validator.split_configs_from_text(text_content)

        for candidate in config_candidates:
            # از طریق پروتکل‌های مرتب شده برای تطبیق اولویت‌دار تکرار کن (خاص‌ترها اول)
            for protocol_name in self.ordered_protocols_for_matching:
                protocol_info = self.active_protocol_info.get(protocol_name)
                
                if protocol_info and isinstance(protocol_info["prefix"], str): # مطمئن شویم پروتکل فعال و پیشوند معتبر دارد
                    # Check if the candidate starts with the prefix for this protocol
                    if candidate.startswith(protocol_info["prefix"]):
                        # NEW: Use the centralized cleaning and validation from ConfigValidator
                        cleaned_candidate = self.config_validator.clean_protocol_config(candidate, protocol_name)
                        
                        if self.config_validator.validate_protocol_config(cleaned_candidate, protocol_name):
                            found_links.append({'protocol': protocol_name, 'link': cleaned_candidate})
                            break # به محض پیدا شدن یک تطابق معتبر برای این قطعه، به کاندیدای بعدی برو
                        # Special handling for "reality" which is a VLESS variant
                        elif protocol_name == "vless":
                            # Check if it's a Reality link using the VLESS validator if it's available
                            vless_validator = self.config_validator.protocol_validators.get("vless")
                            if vless_validator and hasattr(vless_validator, 'is_reality_link') and vless_validator.is_reality_link(cleaned_candidate):
                                found_links.append({'protocol': 'reality', 'link': cleaned_candidate})
                                break

        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """تلاش می‌کند محتوای base64 را با استفاده از متد ConfigValidator رمزگشایی کند."""
        if not settings.ENABLE_BASE64_DECODING:
            return None

        decoded_str = self.config_validator.decode_base64_text(content)
        if decoded_str:
            # بررسی کن آیا محتوای رمزگشایی شده شبیه لیستی از لینک‌ها یا فرمت قابل پارس دیگری است
            # از combined_protocol_prefix_regex برای این بررسی استفاده کن
            if len(decoded_str) > 10 and (self.combined_protocol_prefix_regex.search(decoded_str) or 
                                          self.config_validator.is_valid_protocol_prefix(decoded_str)):
                print("محتوای Base64 با موفقیت رمزگشایی شد و شامل لینک‌های احتمالی است.")
                return decoded_str
            print("Base64 رمزگشایی شد، اما محتوا شامل کانفیگ یا لینک پروتکل معتبر نیست.")
            return None
        return None

    def _parse_clash_config(self, content: str) -> List[Dict]:
        """
        پیکربندی‌های Clash YAML را برای استخراج لینک‌های پروکسی پارس می‌کند.
        """
        if not settings.ENABLE_CLASH_PARSER:
            return []

        extracted_links: List[Dict] = []
        try:
            clash_data = yaml.safe_load(content)
            if not isinstance(clash_data, dict):
                return []

            # استخراج از لیست 'proxies'
            proxies = clash_data.get('proxies', [])
            for proxy_obj in proxies:
                if isinstance(proxy_obj, dict):
                    # تلاش برای بازسازی لینک‌های SS/SSR از دیکشنری، سپس اعتبارسنجی
                    # NEW: This reconstruction logic might ideally go into a specific SS/SSR Validator
                    if proxy_obj.get('type', '').lower() == 'ss' and all(k in proxy_obj for k in ['cipher', 'password', 'server', 'port']):
                        try:
                            # Reconstruct SS link (still needed here if Clash doesn't provide direct links)
                            method_pass = f"{proxy_obj['cipher']}:{proxy_obj['password']}"
                            # Ensure URL-safe base64 encoding if needed by the SS protocol
                            encoded_method_pass = base64.urlsafe_b64encode(method_pass.encode()).decode().rstrip('=')
                            ss_link = f"ss://{encoded_method_pass}@{proxy_obj['server']}:{proxy_obj['port']}"
                            if 'name' in proxy_obj:
                                # Ensure name is URL-encoded for the fragment part
                                from urllib.parse import quote
                                ss_link += f"#{quote(proxy_obj['name'])}"

                            # NEW: Use centralized cleaning and validation
                            cleaned_ss_link = self.config_validator.clean_protocol_config(ss_link, 'ss')
                            if self.config_validator.validate_protocol_config(cleaned_ss_link, 'ss'):
                                extracted_links.append({'protocol': 'ss', 'link': cleaned_ss_link})
                        except Exception as e:
                            print(f"خطا در بازسازی لینک SS از Clash: {e}")

                    # برای انواع دیگر (vmess, vless, trojan)، آن‌ها اغلب لینک‌های مستقیم یا پیچیده هستند.
                    # ما برای یافتن لینک‌های پروتکل مستقیم به جستجو در نمایش رشته JSON تکیه می‌کنیم.
                    proxy_str_representation = json.dumps(proxy_obj)
                    extracted_links.extend(self._extract_direct_links(proxy_str_representation))


            # استخراج از 'proxy-providers' (URLهایی که به اشتراک‌ها اشاره می‌کنند)
            proxy_providers = clash_data.get('proxy-providers', {})
            for provider_name, provider_obj in proxy_providers.items():
                if isinstance(provider_obj, dict) and 'url' in provider_obj:
                    # بررسی کن که URL یک URL http/https معتبر است و به عنوان یک منبع اشتراک اضافه کن
                    if provider_obj['url'].startswith('http://') or provider_obj['url'].startswith('https://'):
                        # No specific validation for subscription links, just add them
                        extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})

            print("پیکربندی Clash با موفقیت پارس شد و لینک‌های احتمالی استخراج شدند.")
        except yaml.YAMLError:
            # print(f"ConfigParser: Invalid YAML format for Clash config.") # For debugging
            pass # پیکربندی YAML (Clash) معتبر نیست
        except Exception as e:
            print(f"ConfigParser: خطا در پارس کردن پیکربندی Clash: {e}")
        return extracted_links

    def _parse_singbox_config(self, content: str) -> List[Dict]:
        """
        پیکربندی‌های SingBox JSON را برای استخراج لینک‌های پروکسی/outbounds پارس می‌کند.
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
                    # تبدیل شیء outbound به رشته برای جستجوی لینک‌هایی مانند vmess://, vless://
                    outbound_str = json.dumps(outbound_obj)
                    extracted_links.extend(self._extract_direct_links(outbound_str))

            print("پیکربندی SingBox با موفقیت پارس شد و لینک‌های احتمالی استخراج شدند.")
        except json.JSONDecodeError:
            # print(f"ConfigParser: Invalid JSON format for SingBox config.") # For debugging
            pass # پیکربندی JSON (SingBox) معتبر نیست
        except Exception as e:
            print(f"ConfigParser: خطا در پارس کردن پیکربندی SingBox: {e}")
        return extracted_links

    def _parse_json_content(self, content: str) -> List[Dict]:
        """
        محتوای JSON عمومی را برای یافتن هر لینک کانفیگ جاسازی شده یا URL اشتراک پارس می‌کند.
        """
        if not settings.ENABLE_JSON_PARSER:
            return []

        extracted_links: List[Dict] = []
        try:
            json_data = json.loads(content)
            json_string = json.dumps(json_data)
            extracted_links.extend(self._extract_direct_links(json_string))
            print("محتوای JSON عمومی با موفقیت پارس شد و لینک‌های احتمالی استخراج شدند.")
        except json.JSONDecodeError:
            # print(f"ConfigParser: Invalid JSON format for generic JSON content.") # For debugging
            pass # JSON معتبر نیست
        except Exception as e:
            print(f"ConfigParser: خطا در پارس کردن محتوای JSON عمومی: {e}")
        return extracted_links


    def parse_content(self, content: str) -> List[Dict]:
        """
        تلاش می‌کند محتوای داده شده را پارس کرده و لینک‌های کانفیگ را با استفاده از روش‌های مختلف استخراج کند.
        لیستی از دیکشنری‌های {'protocol': '...', 'link': '...'} را برمی‌گرداند.
        """
        all_extracted_links: List[Dict] = []

        # ۱. ابتدا لینک‌های مستقیم را از محتوای خام استخراج کن
        direct_links = self._extract_direct_links(content)
        all_extracted_links.extend(direct_links)

        # ۲. رمزگشایی Base64 و سپس پارس کردن محتوای رمزگشایی شده
        decoded_content = self._decode_base64(content)
        if decoded_content:
            # ابتدا، لینک‌های مستقیم را از محتوای رمزگشایی شده استخراج کن
            base64_links = self._extract_direct_links(decoded_content)
            all_extracted_links.extend(base64_links)

            # سپس، تلاش کن محتوای رمزگشایی شده را به عنوان Clash/SingBox/JSON عمومی پارس کنی
            all_extracted_links.extend(self._parse_clash_config(decoded_content))
            all_extracted_links.extend(self._parse_singbox_config(decoded_content))
            all_extracted_links.extend(self._parse_json_content(decoded_content))


        # ۳. پارس کردن Clash (YAML) از محتوای خام
        clash_links = self._parse_clash_config(content)
        all_extracted_links.extend(clash_links)

        # ۴. پارس کردن SingBox (JSON) از محتوای خام
        singbox_links = self._parse_singbox_config(content)
        all_extracted_links.extend(singbox_links)

        # ۵. پارس کردن JSON عمومی از محتوای خام
        json_links = self._parse_json_content(content)
        all_extracted_links.extend(json_links)

        # حذف لینک‌های تکراری قبل از بازگشت
        return list({link['link']: link for link in all_extracted_links}.values())