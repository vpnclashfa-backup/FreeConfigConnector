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
        if not link.startswith("vmess://"):
            return False
        try:
            base64_part = link[8:]
            base64_part_padded = base64_part.replace('-', '+').replace('_', '/')
            missing_padding = len(base64_part_padded) % 4
            if missing_padding != 0:
                base64_part_padded += '=' * (4 - missing_padding)

            decoded_bytes = base64.b64decode(base64_part_padded, validate=True)
            decoded_json_str = decoded_bytes.decode('utf-8')
            config_data = json.loads(decoded_json_str)

            required_fields = ['v', 'ps', 'add', 'port', 'id', 'aid', 'net', 'type']
            if not all(field in config_data for field in required_fields):
                # print(f"VMessValidator: Missing required fields in VMess config: {config_data}") # Debug specific reason
                return False

            if not VmessValidator._is_valid_port(config_data['port']):
                # print(f"VMessValidator: Invalid port in VMess config: {config_data.get('port')}") # Debug specific reason
                return False
            
            if not VmessValidator._is_valid_uuid(config_data['id']):
                # print(f"VMessValidator: Invalid UUID in VMess config: {config_data.get('id')}") # Debug specific reason
                return False
            
            host = config_data['add']
            if not (VmessValidator._is_valid_domain(host) or VmessValidator._is_valid_ip_address(host)):
                # print(f"VMessValidator: Invalid host/IP in VMess config: {host}") # Debug specific reason
                return False

            return True
        except Exception as e:
            print(f"VMessValidator: VMess validation failed for link '{link[:100]}...'. Error: {e}") # Debug specific error
            # traceback.print_exc() # Can uncomment for full traceback if needed
            return False

    @staticmethod
    def clean(link: str) -> str:
        if link.startswith("vmess://"):
            base64_part = link[8:]
            clean_base64_part_match = re.match(r'[A-Za-z0-9+/=_-]*', base64_part)
            if clean_base64_part_match:
                return f"vmess://{clean_base64_part_match.group(0).strip()}"
        return link