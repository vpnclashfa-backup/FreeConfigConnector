import re
import base64
import json
from typing import Optional, Dict

class VmessValidator:
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
            if not isinstance(config_data['port'], int) or not (1 <= config_data['port'] <= 65535):
                return False

            # بررسی ساده UUID
            if not VmessValidator._is_valid_uuid(config_data['id']):
                return False
            
            # (اختیاری) می‌توانید بررسی‌های دقیق‌تر دیگری را در اینجا اضافه کنید
            # مانند بررسی مقادیر معتبر برای 'net', 'type', 'tls' و غیره.

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

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """بررسی می‌کند که آیا یک رشته UUID معتبر است."""
        try:
            # ماژول uuid برای بررسی صحت قالب UUID
            import uuid
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False