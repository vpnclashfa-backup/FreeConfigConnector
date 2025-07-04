from abc import ABC, abstractmethod
from typing import Optional, Union # <--- این خط تغییر کرده (Union اضافه شد)
import re
import ipaddress
import uuid

class BaseValidator(ABC):
    """
    کلاس پایه انتزاعی برای Validatorهای پروتکل‌های پروکسی.
    هر Validator پروتکل باید از این کلاس ارث ببرد و متدهای انتزاعی آن را پیاده‌سازی کند.
    """

    @staticmethod
    @abstractmethod
    def is_valid(link: str) -> bool:
        """
        بررسی می‌کند که آیا یک لینک پروکسی معتبر است یا خیر.
        پیاده‌سازی این متد باید منطق اعتبارسنجی مخصوص پروتکل را در بر گیرد.
        
        Args:
            link (str): لینک پروکسی مورد نظر برای اعتبارسنجی.

        Returns:
            bool: True اگر لینک معتبر باشد، در غیر این صورت False.
        """
        pass

    @staticmethod
    @abstractmethod
    def clean(link: str) -> str:
        """
        لینک پروکسی را پاکسازی می‌کند (مثلاً کاراکترهای اضافی را حذف می‌کند).
        پیاده‌سازی این متد باید منطق پاکسازی مخصوص پروتکل را در بر گیرد.
        
        Args:
            link (str): لینک پروکسی مورد نظر برای پاکسازی.

        Returns:
            str: لینک پاکسازی شده.
        """
        pass

    @staticmethod
    def _is_valid_ipv4(ip: str) -> bool:
        """بررسی می‌کند که آیا یک رشته آدرس IPv4 معتبر است."""
        try:
            return isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
        except ValueError:
            return False

    @staticmethod
    def _is_valid_ipv6(ip: str) -> bool:
        """بررسی می‌کند که آیا یک رشته آدرس IPv6 معتبر است."""
        try:
            return isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
        except ValueError:
            return False

    @staticmethod
    def _is_valid_ip_address(ip: str) -> bool:
        """بررسی می‌کند که آیا یک رشته آدرس IP (IPv4 یا IPv6) معتبر است. همچنین IPV6 محصور در [] را مدیریت می‌کند."""
        if ip.startswith("[") and ip.endswith("]"):
            ip = ip[1:-1]
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_valid_domain(hostname: str) -> bool:
        """بررسی می‌کند که آیا یک رشته نام دامنه معتبر است."""
        if not hostname or len(hostname) > 255:
            return False
        if hostname.endswith("."):
            hostname = hostname[:-1]
        return all(re.match(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$", x) for x in hostname.split("."))

    @staticmethod
    def _is_valid_port(port: Union[int, str]) -> bool: # <--- اینجا Union استفاده شده
        """بررسی می‌کند که آیا یک پورت عددی معتبر است."""
        try:
            port_int = int(port)
            return 1 <= port_int <= 65535
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """بررسی می‌کند که آیا یک رشته UUID معتبر است."""
        try:
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False