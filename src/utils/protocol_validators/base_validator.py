from abc import ABC, abstractmethod
from typing import Optional, Union # Ensure Union is imported and used
import re
import ipaddress # Used for IP address validation
import uuid # Used for UUID validation

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

    # --- Common Helper Static Methods for Validation ---

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
            ip = ip[1:-1] # Remove brackets for IPv6 address validation
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
            hostname = hostname[:-1] # Remove trailing dot if present
        
        # Regex for valid domain labels (parts separated by dots)
        # Each label must be 1-63 characters long, start and end with an alphanumeric character,
        # and contain only alphanumeric characters or hyphens.
        # This is a strict check for standard domain names.
        domain_label_pattern = re.compile(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$")
        return all(domain_label_pattern.match(x) for x in hostname.split("."))

    @staticmethod
    def _is_valid_port(port: Union[int, str]) -> bool:
        """بررسی می‌کند که آیا یک پورت عددی معتبر است (بین 1 تا 65535)."""
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