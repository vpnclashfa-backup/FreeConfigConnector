import re
import base64
import json
from typing import Optional, Dict
from urllib.parse import urlparse
from src.utils.protocol_validators.base_validator import BaseValidator

class VmessValidator(BaseValidator):
    """
    اعتبارسنجی و پاکسازی لینک‌های پروتکل VMess.
    """

    @staticmethod
    def is_valid(link: str) -> bool:
        """
        بررسی می‌کند که آیا لینک VMess معتبر است یا خیر.
        این شامل بررسی ساختار base64 و محتوای JSON رمزگشایی شده است.
        """
        if not link.startswith("vmess://"):
            return False
        try:
            base64_part = link[8:]
            # برخی لینک‌ها ممکن است به درستی padding نشده باشند. base64.urlsafe_b64decode می تواند کمک کند.
            # برای اطمینان بیشتر، قبل از decode پدینگ مناسب را اضافه می‌کنیم.
            base64_part_padded = base64_part.replace('-', '+').replace('_', '/')
            missing_padding = len(base64_part_padded) % 4
            if missing_padding != 0:
                base64_part_padded += '=' * (4 - missing_padding)

            decoded_bytes = base64.b64decode(base64_part_padded, validate=True)
            decoded_json_str = decoded_bytes.decode('utf-8')
            config_data = json.loads(decoded_json_str)

            # بررسی حداقل فیلدهای ضروری برای یک کانفیگ VMess معتبر
            required_fields = ['v', 'ps', 'add', 'port', 'id', 'aid', 'net', 'type']
            if not all(field in config_data for field in required_fields):
                return False

            # بررسی نوع فیلدها (مثال: پورت باید عدد باشد)
            if not VmessValidator._is_valid_port(config_data['port']):
                return False

            # بررسی ساده UUID
            if not VmessValidator._is_valid_uuid(config_data['id']):
                return False
            
            # (اختیاری) می‌توانید بررسی‌های دقیق‌تر دیگری را در اینجا اضافه کنید
            # مانند بررسی مقادیر معتبر برای 'net', 'type', 'tls' و غیره.
            # مثال:
            # if config_data['net'] not in ['tcp', 'ws', 'h2', 'quic', 'grpc']: return False
            # if not VmessValidator._is_valid_domain(config_data['add']) and not VmessValidator._is_valid_ip_address(config_data['add']): return False

            return True
        except Exception as e:
            # print(f"VMess validation failed for {link}: {e}") # برای دیباگ
            return False

    @staticmethod
    def clean(link: str) -> str:
        """
        لینک VMess را پاکسازی می‌کند.
        هر کاراکتر اضافی را بعد از بخش base64 معتبر حذف می‌کند.
        """
        if link.startswith("vmess://"):
            base64_part = link[8:]
            # فقط کاراکترهای معتبر base64 را نگه می‌دارد (حتی اگر padding نداشته باشند)
            clean_base64_part_match = re.match(r'[A-Za-z0-9+/=_-]*', base64_part)
            if clean_base64_part_match:
                return f"vmess://{clean_base64_part_match.group(0).strip()}"
        return link

    # متدهای کمکی دیگر مخصوص VMess می‌توانند اینجا اضافه شوند
    # متدهای _is_valid_uuid, _is_valid_port, _is_valid_ip_address, _is_valid_domain
    # از BaseValidator به ارث برده شده و نیازی به تعریف مجدد نیست.
    # فقط به عنوان VmessValidator._is_valid_uuid (یا self._is_valid_uuid داخل متدهای دیگر همین کلاس) قابل دسترسی هستند.