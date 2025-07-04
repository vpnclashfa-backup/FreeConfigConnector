import re
from typing import Dict, List, Type, Union

from src.utils.protocol_validators.base_validator import BaseValidator
from src.utils.protocol_validators.vmess_validator import VmessValidator
from src.utils.protocol_validators.vless_validator import VlessValidator
from src.utils.protocol_validators.http_validator import HttpValidator
from src.utils.protocol_validators.socks5_validator import Socks5Validator
from src.utils.protocol_validators.ss_validator import SsValidator
from src.utils.protocol_validators.ssr_validator import SsrValidator
from src.utils.protocol_validators.trojan_validator import TrojanValidator
from src.utils.protocol_validators.hysteria_validator import HysteriaValidator
from src.utils.protocol_validators.hysteria2_validator import Hysteria2Validator
from src.utils.protocol_validators.tuic_validator import TuicValidator
from src.utils.protocol_validators.wireguard_validator import WireguardValidator
from src.utils.protocol_validators.ssh_validator import SshValidator
from src.utils.protocol_validators.warp_validator import WarpValidator
from src.utils.protocol_validators.juicity_validator import JuicityValidator
from src.utils.protocol_validators.mieru_validator import MieruValidator
from src.utils.protocol_validators.snell_validator import SnellValidator
from src.utils.protocol_validators.anytls_validator import AnytlsValidator


from src.utils.settings_manager import settings

# Define base protocol information including their prefixes and their validator classes.
PROTOCOL_INFO_MAP: Dict[str, Dict[str, Union[str, Type[BaseValidator]]]] = {
    "http": {"prefix": "http://", "validator": HttpValidator},
    "socks5": {"prefix": "socks5://", "validator": Socks5Validator},
    "ss": {"prefix": "ss://", "validator": SsValidator},
    "ssr": {"prefix": "ssr://", "validator": SsrValidator},
    "vmess": {"prefix": "vmess://", "validator": VmessValidator},
    "vless": {"prefix": "vless://", "validator": VlessValidator},
    "trojan": {"prefix": "trojan://", "validator": TrojanValidator},
    "hysteria": {"prefix": "hysteria://", "validator": HysteriaValidator},
    "hysteria2": {"prefix": "hy2://", "validator": Hysteria2Validator},
    "tuic": {"prefix": "tuic://", "validator": TuicValidator},
    "wireguard": {"prefix": "wireguard://", "validator": WireguardValidator},
    "ssh": {"prefix": "ssh://", "validator": SshValidator},
    "warp": {"prefix": "warp://", "validator": WarpValidator},
    "juicity": {"prefix": "juicity://", "validator": JuicityValidator},
    "mieru": {"prefix": "mieru://", "validator": MieruValidator},
    "snell": {"prefix": "snell://", "validator": SnellValidator},
    "anytls": {"prefix": "anytls://", "validator": AnytlsValidator},
}

ORDERED_PROTOCOLS_FOR_MATCHING: List[str] = [
    "reality",
    "vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2",
    "tuic", "wireguard", "ssh", "warp", "juicity", "http", "socks5",
    "mieru", "snell", "anytls"
]


def get_active_protocol_info() -> Dict[str, Dict[str, Union[str, Type[BaseValidator]]]]:
    active_info: Dict[str, Dict[str, Union[str, Type[BaseValidator]]]] = {}
    for protocol_name in settings.ACTIVE_PROTOCOLS:
        if protocol_name in PROTOCOL_INFO_MAP:
            active_info[protocol_name] = PROTOCOL_INFO_MAP[protocol_name]
        else:
            if protocol_name != 'reality':
                print(f"protocol_definitions: WARNING: Protocol '{protocol_name}' in settings.ACTIVE_PROTOCOLS is not defined in PROTOCOL_INFO_MAP. Using generic handler.")
            active_info[protocol_name] = {"prefix": f"{protocol_name}://", "validator": BaseValidator}
    return active_info

def get_combined_protocol_full_regex() -> re.Pattern:
    """
    Returns a compiled RegEx pattern that can detect the *full* link of any active protocol.
    This version constructs a safer regex by first defining allowed URL characters broadly,
    and then using that character set within the pattern, enclosed in a non-capturing group.
    This avoids issues with malformed subpatterns.
    """
    active_protocols_info = get_active_protocol_info()
    
    # Define a set of characters that are generally allowed in URLs
    # This includes alphanumeric, common symbols, and URL-encoded characters.
    # Excludes: whitespace, single/double quotes, angle brackets.
    # Note: # is allowed inside URL, but can be a delimiter for tags, which is handled later.
    # Parentheses () are allowed in some URL contexts but can cause regex issues if not properly handled in complex patterns.
    # For safety, let's include all common URL characters and Persian characters.
    # Exclude characters that are definitely NOT part of a link:
    # \s (whitespace), ' " < >
    # Using \S (any non-whitespace) and then explicitly excluding.
    
    # This character set is for the *content* of the URL part.
    # It must handle URL-encoded characters like %2F, %3D, etc.
    # So, allowing % and then any alphanumeric.
    url_char_set = r"[a-zA-Z0-9\-\._~:/?#\[\]@!$&'()*+,;%=\u0600-\u06FF]" # General URL characters + Persian script
    
    # Build patterns for each protocol: (?:prefix://[allowed_chars_in_url]+)
    full_patterns_list = []
    for info in active_protocols_info.values():
        prefix = info.get("prefix")
        if isinstance(prefix, str):
            # Escape the prefix to treat its literal value, then add the URL character class.
            # Using a non-capturing group (?:...) for the whole pattern.
            full_patterns_list.append(r"(?:" + re.escape(prefix) + url_char_set + r"+)")

    # Special handling for "ssh" if it needs alternative prefixes like "sftp://".
    if "ssh" in settings.ACTIVE_PROTOCOLS and "sftp://" not in [info.get("prefix") for info in active_protocols_info.values()]:
        full_patterns_list.append(r"(?:" + re.escape("sftp://") + url_char_set + r"+)")

    # Join all individual protocol patterns with '|' (OR)
    combined_full_regex_str = '|'.join(full_patterns_list)
    print(f"protocol_definitions: Generated combined FULL regex string: {combined_full_regex_str}")

    if not combined_full_regex_str:
        print("protocol_definitions: WARNING: No active protocols found to build combined FULL regex. Returning empty match regex.")
        return re.compile(r'a^')

    # Compile the final regex with UNICODE flag for Persian characters and IGNORECASE for prefixes.
    # re.DOTALL is generally not needed here as we want line-by-line matching, and newline is a \s.
    return re.compile(combined_full_regex_str, re.IGNORECASE | re.UNICODE)