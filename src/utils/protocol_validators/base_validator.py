from abc import ABC, abstractmethod
from typing import Optional

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
        pass # این متد باید توسط کلاس‌های فرزند پیاده‌سازی شود

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
        pass # این متد باید توسط کلاس‌های فرزند پیاده‌سازی شود

    # می‌توانید متدهای کمکی مشترک را در اینجا اضافه کنید، 
    # اما مطمئن شوید که متدهای abstract@ را حفظ می‌کنید.

    @staticmethod
    def _is_valid_ipv4(ip: str) -> bool:
        """بررسی می‌کند که آیا یک رشته آدرس IPv4 معتبر است."""
        try:
            import ipaddress
            return isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address)
        except ValueError:
            return False

    @staticmethod
    def _is_valid_ipv6(ip: str) -> bool:
        """بررسی می‌کند که آیا یک رشته آدرس IPv6 معتبر است."""
        try:
            import ipaddress
            return isinstance(ipaddress.ip_address(ip), ipaddress.IPv6Address)
        except ValueError:
            return False

    @staticmethod
    def _is_valid_domain(hostname: str) -> bool:
        """بررسی می‌کند که آیا یک رشته نام دامنه معتبر است."""
        if not hostname or len(hostname) > 255:
            return False
        if hostname.endswith("."):
            hostname = hostname[:-1] # Remove trailing dot if present
        # رگولار اکسپرشن برای بررسی بخش‌های دامنه
        import re
        return all(re.match(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$", x) for x in hostname.split("."))

    @staticmethod
    def _is_valid_port(port: int) -> bool:
        """بررسی می‌کند که آیا یک پورت عددی معتبر است."""
        return isinstance(port, int) and 1 <= port <= 65535

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """بررسی می‌کند که آیا یک رشته UUID معتبر است."""
        try:
            import uuid
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False