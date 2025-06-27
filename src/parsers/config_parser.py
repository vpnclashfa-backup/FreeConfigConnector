# src/parsers/config_parser.py

import base64
import json
import re
import yaml # pip install PyYAML
from typing import List, Dict, Optional, Tuple

# وارد کردن تعاریف پروتکل مرکزی و ConfigValidator
from src.utils.protocol_definitions import get_protocol_regex_patterns, get_combined_protocol_regex
from src.utils.config_validator import ConfigValidator 

# استفاده مستقیم از تنظیمات از utils
from src.utils.settings_manager import settings


class ConfigParser:
    def __init__(self):
        self.protocol_regex_patterns_map = get_protocol_regex_patterns()
        self.config_validator = ConfigValidator()
        
        # کامپایل کردن الگوها برای کارایی بیشتر (جهت جستجو در متن)
        self.compiled_patterns = {
            p: re.compile(pattern, re.IGNORECASE) 
            for p, pattern in self.protocol_regex_patterns_map.items()
        }
        
        self.combined_protocol_regex = get_combined_protocol_regex()

        # لیست مرتب شده از نام پروتکل‌ها برای تطبیق اولویت‌دار.
        # Reality باید قبل از VLESS عمومی بررسی شود.
        self.ordered_protocols_for_matching: List[str] = [
            "reality", # Reality را ابتدا بررسی کن زیرا یک نوع VLESS با پارامترهای خاص است
            "vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2",
            "tuic", "wireguard", "ssh", "warp", "juicity", "http", "https", "socks5",
            "mieru", "snell", "anytls"
            # اطمینان حاصل شود که این لیست تمامی active_protocols از تنظیمات را پوشش می‌دهد
            # ترتیب در اینجا برای طبقه‌بندی دقیق (خاص‌ترها اول) حیاتی است
        ]


    def _extract_direct_links(self, text_content: str) -> List[Dict]:
        """
        لینک‌های پروتکل مستقیم را از هر محتوای متنی استخراج می‌کند.
        این تابع اکنون از ConfigValidator.split_configs_from_text
        برای تقسیم متن به رشته‌های کانفیگ‌مانند معتبر استفاده می‌کند.
        """
        found_links: List[Dict] = []
        
        # از متد تقسیم‌بندی اعتبارسنج برای به دست آوردن قطعات کانفیگ تمیز احتمالی استفاده کن
        config_candidates = self.config_validator.split_configs_from_text(text_content, self.combined_protocol_regex)

        for candidate in config_candidates:
            # از طریق پروتکل‌های مرتب شده برای تطبیق اولویت‌دار تکرار کن
            for protocol_name in self.ordered_protocols_for_matching:
                # بررسی کن که آیا کاندیدا با الگوی این پروتکل تطابق دارد و فعال است
                if protocol_name in self.protocol_regex_patterns_map: # بررسی کن آیا این پروتکل در تنظیمات فعال است
                    compiled_pattern = self.compiled_patterns[protocol_name]
                    # از match() استفاده کن تا بررسی کنی آیا کاندیدا با الگو از ابتدا تطابق دارد
                    if compiled_pattern.match(candidate): 
                        # اعتبارسنجی عمیق‌تر کانفیگ استخراج شده با اعتبارسنجی پروتکل خاص
                        # نام پروتکل را (مثلاً 'vmess') نه 'vmess://' کامل را پاس بده
                        if self.config_validator.validate_protocol_config(candidate, protocol_name):
                            found_links.append({'protocol': protocol_name, 'link': candidate})
                            break # به محض پیدا شدن یک تطابق معتبر برای این قطعه، به کاندیدای بعدی برو
            
        return found_links

    def _decode_base64(self, content: str) -> Optional[str]:
        """تلاش می‌کند محتوای base64 را با استفاده از متد ConfigValidator رمزگشایی کند."""
        if not settings.ENABLE_BASE64_DECODING:
            return None
        
        decoded_str = self.config_validator.decode_base64_text(content)
        if decoded_str:
            # بررسی کن آیا محتوای رمزگشایی شده شبیه لیستی از لینک‌ها یا فرمت قابل پارس دیگری است
            if len(decoded_str) > 10 and (self.combined_protocol_regex.search(decoded_str) or 
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
                        extracted_links.append({'protocol': 'subscription', 'link': provider_obj['url']})
            
            print("پیکربندی Clash با موفقیت پارس شد و لینک‌های احتمالی استخراج شدند.")
        except yaml.YAMLError:
            pass # پیکربندی YAML (Clash) معتبر نیست
        except Exception as e:
            print(f"خطا در پارس کردن پیکربندی Clash: {e}")
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
            pass # پیکربندی JSON (SingBox) معتبر نیست
        except Exception as e:
            print(f"خطا در پارس کردن پیکربندی SingBox: {e}")
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
            pass # JSON معتبر نیست
        except Exception as e:
            print(f"خطا در پارس کردن محتوای JSON عمومی: {e}")
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
