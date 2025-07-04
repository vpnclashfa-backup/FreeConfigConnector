import re
import json
from typing import Optional, Dict
from urllib.parse import urlparse, parse_qs, unquote
from src.utils.protocol_validators.base_validator import BaseValidator

class VlessValidator(BaseValidator):
    """
    اعتبارسنجی و پاکسازی لینک‌های پروتکل VLESS.
    """

    @staticmethod
    def is_valid(link: str) -> bool:
        """
        بررسی می‌کند که آیا لینک VLESS معتبر است یا خیر.
        """
        if not link.startswith("vless://"):
            return False
        try:
            parsed_url = urlparse(link)

            # Decode the userinfo part (UUID@host:port)
            userinfo_part = parsed_url.netloc
            if '@' not in userinfo_part:
                return False # Expected format: UUID@host:port

            uuid_str, host_port = userinfo_part.split('@', 1)

            if not VlessValidator._is_valid_uuid(uuid_str):
                return False

            if ':' not in host_port:
                return False # Expected format: host:port

            host, port_str = host_port.rsplit(':', 1) # Use rsplit to handle IPv6 addresses with colons

            if not VlessValidator._is_valid_port(int(port_str)):
                return False

            if not VlessValidator._is_valid_domain(host) and \
               not VlessValidator._is_valid_ipv4(host) and \
               not VlessValidator._is_valid_ipv6(host):
                return False

            # Check query parameters for necessary fields if needed (e.g., type=ws, security=tls, flow, reality)
            query_params = parse_qs(parsed_url.query)

            # Basic check for 'type' (network type like ws, grpc etc.)
            if 'type' in query_params and query_params['type'][0] not in ['tcp', 'ws', 'grpc', 'h2', 'quic']:
                return False

            # Basic check for 'security' (tls, reality)
            if 'security' in query_params and query_params['security'][0] not in ['tls', 'reality', 'none']:
                return False

            # If 'security=reality', make sure 'pbk' is present (basic check, can be more thorough)
            if query_params.get('security', [''])[0] == 'reality' and 'pbk' not in query_params:
                # For Reality, check for some common reality parameters
                return False # Minimal check for reality

            return True
        except ValueError:
            return False # Port conversion failed
        except Exception as e:
            # print(f"VLESS validation failed for {link}: {e}") # For debugging
            return False

    @staticmethod
    def clean(link: str) -> str:
        """
        پاکسازی لینک VLESS.
        هر کاراکتر اضافی را بعد از بخش معتبر لینک VLESS حذف می‌کند.
        """
        # VLESS links are generally self-contained, but sometimes have trailing junk.
        # We can use the same trailing junk pattern from ConfigValidator.split_configs_from_text if needed.
        # For now, a simple strip should suffice as ConfigValidator handles main junk removal.
        cleaned_link = link.strip()
        return cleaned_link

    @staticmethod
    def is_reality_link(link: str) -> bool:
        """
        بررسی می‌کند که آیا یک لینک VLESS خاص یک لینک Reality است.
        این متد توسط ConfigParser برای تشخیص "reality" فراخوانی می‌شود.
        """
        if not link.startswith("vless://"):
            return False
        try:
            parsed_url = urlparse(link)
            query_params = parse_qs(parsed_url.query)
            return query_params.get('security', [''])[0] == 'reality'
        except Exception:
            return False