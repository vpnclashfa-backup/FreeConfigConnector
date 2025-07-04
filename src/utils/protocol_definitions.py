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
            if protocol_name != 'reality': # 'reality' has no fixed prefix like 'reality://', so it's a special case regex in ConfigValidator.
                print(f"protocol_definitions: WARNING: Protocol '{protocol_name}' in settings.ACTIVE_PROTOCOLS is not defined in PROTOCOL_INFO_MAP. Using generic handler.")
            active_info[protocol_name] = {"prefix": f"{protocol_name}://", "validator": BaseValidator}
    return active_info

def get_combined_protocol_full_regex() -> re.Pattern:
    """
    Returns a compiled RegEx pattern that can detect the *full* link of any active protocol.
    This version focuses on robustness against common regex syntax errors in URLs
    by using a broad character match for the URL content, ensuring the pattern itself is well-formed.
    It primarily aims to fix "unterminated subpattern" errors.
    """
    active_protocols_info = get_active_protocol_info()
    
    full_patterns_list = []
    
    # Generic URL matching part: matches any character (except newline by default) zero or more times,
    # until a whitespace character is encountered, or the end of the string.
    # This is safer than explicitly listing all URL characters, as it avoids missing any.
    # It also avoids issues with regex special characters within the URL content itself.
    url_content_pattern = r'[^\s"\']+' # Matches any non-whitespace, non-quote character. More robust for splitting.

    for info in active_protocols_info.values():
        prefix = info.get("prefix")
        if isinstance(prefix, str):
            # Escape the literal prefix to ensure it's matched exactly.
            # Then, append the broad URL content pattern.
            # The entire unit is a non-capturing group.
            full_patterns_list.append(r"(?:" + re.escape(prefix) + url_content_pattern + r")")

    # Special handling for "ssh" if it needs alternative prefixes like "sftp://".
    # Ensure this is only added once if not already present via PROTOCOL_INFO_MAP.
    if "ssh" in settings.ACTIVE_PROTOCOLS and "sftp://" not in [info.get("prefix") for info in active_protocols_info.values()]:
        full_patterns_list.append(r"(?:" + re.escape("sftp://") + url_content_pattern + r")")
    
    # Also add specific patterns for protocols that might not start with "protocol://" but have other well-defined structures.
    # For instance, a common pattern for "reality" might start with "reality", but not necessarily "reality://".
    # For now, "reality" handling is left to specific heuristic in ConfigParser.
    
    combined_full_regex_str = '|'.join(full_patterns_list)
    print(f"protocol_definitions: Generated combined FULL regex string: {combined_full_regex_str}")

    if not combined_full_regex_str:
        print("protocol_definitions: WARNING: No active protocols found to build combined FULL regex. Returning empty match regex.")
        return re.compile(r'a^') # This regex will never match anything.

    # Compile the final regex with UNICODE flag for potentially broad character sets and IGNORECASE for prefixes.
    # re.DOTALL is not typically needed here as we want to capture within lines, not across them.
    # The [^\s"\']+ prevents matching beyond the actual link if it's followed by text.
    return re.compile(combined_full_regex_str, re.IGNORECASE | re.UNICODE)

