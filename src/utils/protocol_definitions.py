import re
from typing import Dict, List, Type
# NEW: Import the abstract base class for validators and specific validators
from src.utils.protocol_validators.base_validator import BaseValidator
from src.utils.protocol_validators.vmess_validator import VmessValidator
# Import other specific validators here as you create them
# from src.utils.protocol_validators.vless_validator import VlessValidator
# from src.utils.protocol_validators.trojan_validator import TrojanValidator
# ...

from src.utils.settings_manager import settings

# Define base protocol information including their prefixes and their validator classes.
# This is the central registry for protocols.
PROTOCOL_INFO_MAP: Dict[str, Dict[str, str | Type[BaseValidator]]] = {
    "http": {"prefix": "http://", "validator": BaseValidator}, # Use BaseValidator for generic validation
    "socks5": {"prefix": "socks5://", "validator": BaseValidator},
    "ss": {"prefix": "ss://", "validator": BaseValidator}, # Placeholder, create specific SSValidator later
    "ssr": {"prefix": "ssr://", "validator": BaseValidator}, # Placeholder, create specific SSRValidator later
    "vmess": {"prefix": "vmess://", "validator": VmessValidator}, # Specific VMess validator
    "vless": {"prefix": "vless://", "validator": BaseValidator}, # Placeholder, create specific VlessValidator later
    "trojan": {"prefix": "trojan://", "validator": BaseValidator}, # Placeholder, create specific TrojanValidator later
    "hysteria": {"prefix": "hysteria://", "validator": BaseValidator},
    "hysteria2": {"prefix": "hy2://", "validator": BaseValidator}, # Hysteria2 often uses hy2://, handle in validator if needed
    "tuic": {"prefix": "tuic://", "validator": BaseValidator},
    "wireguard": {"prefix": "wireguard://", "validator": BaseValidator},
    "ssh": {"prefix": "ssh://", "validator": BaseValidator},
    "warp": {"prefix": "warp://", "validator": BaseValidator},
    "juicity": {"prefix": "juicity://", "validator": BaseValidator},
    "mieru": {"prefix": "mieru://", "validator": BaseValidator},
    "snell": {"prefix": "snell://", "validator": BaseValidator},
    "anytls": {"prefix": "anytls://", "validator": BaseValidator},
    # Add other protocols here with their specific validators when created
}

# Define an ordered list of protocols for matching. More specific protocols first.
# This is important for cases like Reality (VLESS) which needs to be identified before generic VLESS.
ORDERED_PROTOCOLS_FOR_MATCHING: List[str] = [
    "reality", # Although not a direct prefix, it's a VLESS variant; handle its detection logic in VlessValidator
    "vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2",
    "tuic", "wireguard", "ssh", "warp", "juicity", "http", "socks5",
    "mieru", "snell", "anytls"
]


def get_active_protocol_info() -> Dict[str, Dict[str, str | Type[BaseValidator]]]:
    """
    Returns a map of active protocols to their full information (prefix, validator class).
    Filters based on settings.ACTIVE_PROTOCOLS.
    """
    active_info: Dict[str, Dict[str, str | Type[BaseValidator]]] = {}
    for protocol_name in settings.ACTIVE_PROTOCOLS:
        if protocol_name in PROTOCOL_INFO_MAP:
            active_info[protocol_name] = PROTOCOL_INFO_MAP[protocol_name]
        else:
            print(f"Warning: Protocol '{protocol_name}' in settings.ACTIVE_PROTOCOLS is not defined in PROTOCOL_INFO_MAP. Using generic handler.")
            active_info[protocol_name] = {"prefix": f"{protocol_name}://", "validator": BaseValidator}
    return active_info

def get_combined_protocol_prefix_regex() -> re.Pattern:
    """
    Returns a compiled RegEx pattern that can detect the *start* of any active protocol.
    This is used for splitting long texts into potential config segments.
    """
    active_protocols_info = get_active_protocol_info()
    
    # Create a regex that matches the *start* of any active protocol (e.g., 'vless://', 'ss://')
    # Escape the prefix to handle special regex characters like . or :
    protocol_prefixes = [re.escape(info["prefix"]) for info in active_protocols_info.values() if isinstance(info["prefix"], str)]

    # Special handling for "ssh" if it needs alternative prefixes like "sftp://"
    # If your SSH validator handles both "ssh://" and "sftp://", add "sftp://" to protocol_prefixes
    # Example: if "ssh" in active_protocols_info: protocol_prefixes.append(re.escape("sftp://"))

    combined_prefix_regex_str = '|'.join(protocol_prefixes)

    if not combined_prefix_regex_str:
        return re.compile(r'a^') # Matches nothing if no protocols are active

    # Use re.IGNORECASE for case-insensitive prefix matching (e.g., Vmess:// or vmess://)
    return re.compile(combined_prefix_regex_str, re.IGNORECASE)