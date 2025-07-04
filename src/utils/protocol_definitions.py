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
# This is the central registry for protocols.
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

def get_combined_protocol_full_regex() -> re.Pattern: # <-- Function name changed to reflect "full" regex
    """
    Returns a compiled RegEx pattern that can detect the *full* link of any active protocol.
    This is used for splitting long texts into potential config segments more accurately.
    """
    active_protocols_info = get_active_protocol_info()
    
    # We need to build patterns like (?:vmess://[^\s]+) or (?:vless://[^\s]+)
    # The [^\s]+ part captures everything until a whitespace or end of string.
    full_patterns_list = []
    for info in active_protocols_info.values():
        prefix = info.get("prefix")
        if isinstance(prefix, str):
            # Escape the prefix and then append the non-whitespace capture group
            full_patterns_list.append(r"(?:" + re.escape(prefix) + r"[^\s]+)")

    # Special handling for "ssh" if it needs alternative prefixes like "sftp://"
    if "ssh" in settings.ACTIVE_PROTOCOLS and "sftp://" not in [info.get("prefix") for info in active_protocols_info.values()]:
        full_patterns_list.append(r"(?:" + re.escape("sftp://") + r"[^\s]+)") # Add sftp prefix as a full pattern


    combined_full_regex_str = '|'.join(full_patterns_list)
    print(f"protocol_definitions: Generated combined FULL regex string: {combined_full_regex_str}")

    if not combined_full_regex_str:
        print("protocol_definitions: WARNING: No active protocols found to build combined FULL regex. Returning empty match regex.")
        return re.compile(r'a^')

    # Use re.IGNORECASE for case-insensitive matching
    return re.compile(combined_full_regex_str, re.IGNORECASE)