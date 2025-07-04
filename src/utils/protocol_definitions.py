import re
from typing import Dict, List, Type, Union # ADDED Union import
# NEW: Import the abstract base class for validators and specific validators
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
# CHANGED: Use Union[str, Type[BaseValidator]] instead of str | Type[BaseValidator]
PROTOCOL_INFO_MAP: Dict[str, Dict[str, Union[str, Type[BaseValidator]]]] = {
    "http": {"prefix": "http://", "validator": HttpValidator}, # Now uses specific validator
    "socks5": {"prefix": "socks5://", "validator": Socks5Validator}, # Now uses specific validator
    "ss": {"prefix": "ss://", "validator": SsValidator}, # Now uses specific validator
    "ssr": {"prefix": "ssr://", "validator": SsrValidator}, # Now uses specific validator
    "vmess": {"prefix": "vmess://", "validator": VmessValidator}, # Specific VMess validator
    "vless": {"prefix": "vless://", "validator": VlessValidator}, # Specific Vless validator
    "trojan": {"prefix": "trojan://", "validator": TrojanValidator}, # Now uses specific validator
    "hysteria": {"prefix": "hysteria://", "validator": HysteriaValidator}, # Now uses specific validator
    "hysteria2": {"prefix": "hy2://", "validator": Hysteria2Validator}, # Now uses specific validator
    "tuic": {"prefix": "tuic://", "validator": TuicValidator}, # Now uses specific validator
    "wireguard": {"prefix": "wireguard://", "validator": WireguardValidator}, # Now uses specific validator
    "ssh": {"prefix": "ssh://", "validator": SshValidator}, # Now uses specific validator
    "warp": {"prefix": "warp://", "validator": WarpValidator}, # Now uses specific validator
    "juicity": {"prefix": "juicity://", "validator": JuicityValidator}, # Now uses specific validator
    "mieru": {"prefix": "mieru://", "validator": MieruValidator}, # Now uses specific validator
    "snell": {"prefix": "snell://", "validator": SnellValidator}, # Now uses specific validator
    "anytls": {"prefix": "anytls://", "validator": AnytlsValidator}, # Now uses specific validator
    # Add other protocols here with their specific validators when created
}

# Define an ordered list of protocols for matching. More specific protocols first.
# This is important for cases like Reality (VLESS) which needs to be identified before generic VLESS.
ORDERED_PROTOCOLS_FOR_MATCHING: List[str] = [
    "reality", # Although not a direct prefix, it's a VLESS variant; handle its detection logic in VlessValidator
    "vmess", "vless", "trojan", "ss", "ssr", "hysteria", "hysteria2",
    "tuic", "wireguard", "ssh", "warp", "juicity", "http", "socks5",
    "mieru", "snell", "anytls"
    # Ensure this list covers all active_protocols from settings
    # The order here is crucial for accurate categorization (more specific ones first)
]


def get_active_protocol_info() -> Dict[str, Dict[str, Union[str, Type[BaseValidator]]]]: # CHANGED: Use Union
    """
    Returns a map of active protocols to their full information (prefix, validator class).
    Filters based on settings.ACTIVE_PROTOCOLS.
    """
    active_info: Dict[str, Dict[str, Union[str, Type[BaseValidator]]]] = {} # CHANGED: Use Union
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
    if "ssh" in active_protocols_info: 
        protocol_prefixes.append(re.escape("sftp://")) # Add sftp prefix if ssh is active


    combined_prefix_regex_str = '|'.join(protocol_prefixes)

    if not combined_prefix_regex_str:
        return re.compile(r'a^') # Matches nothing if no protocols are active

    # Use re.IGNORECASE for case-insensitive prefix matching (e.g., Vmess:// or vmess://)
    return re.compile(combined_prefix_regex_str, re.IGNORECASE)