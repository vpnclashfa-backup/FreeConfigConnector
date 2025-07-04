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
    This is used for splitting long texts into potential config segments more accurately.
    The pattern now explicitly excludes common non-URL/non-link-ending characters
    such as quotes, angle brackets, and non-ASCII whitespace/control characters.
    It also includes common URL-safe characters explicitly.
    """
    active_protocols_info = get_active_protocol_info()
    
    full_patterns_list = []
    for info in active_protocols_info.values():
        prefix = info.get("prefix")
        if isinstance(prefix, str):
            # Escape the prefix and then append a more robust capture group for URL characters.
            # This pattern means: capture anything that is NOT a space, quote (single/double),
            # angle bracket (< >), or hash (#, unless part of a URL fragment).
            # We'll rely on validators to properly handle the # part and URL decoding.
            # Also, explicitly include common URL safe characters and Persian characters (for tags/host)
            # Unicode character range for common Persian/Arabic characters: \u0600-\u06FF
            # Combining these for robustness.
            # Also exclude common emoji ranges if they cause issues.
            
            # Pattern to match characters typical in a URL or its parameters/fragment,
            # excluding common delimiters and problematic text-embedding characters.
            # [^"'\s<>#]+ -- this was the previous.
            # Let's expand on characters:
            # - Basic URL safe: a-zA-Z0-9\-\._~:/?#\[\]@!$&'()*+,;%=
            # - Common in tags/usernames: \u0600-\u06FF (Persian/Arabic)
            # - Exclusions that are still present in content: control chars, zero-width chars (already removed by clean_string_for_splitting)
            #   We need to ensure it stops at actual end of link, not just any whitespace.
            #   Using [^\s]+ is usually fine IF the cleaning ensures no internal bad chars.
            #   The specific problem "missing ), unterminated subpattern" indicates a regex parsing error,
            #   which can happen if a regex is malformed due to an unescaped character *within* the captured part,
            #   or if the regex engine itself has issues with very long/complex patterns from combined sources.

            # Let's simplify the capture group: match typical URL characters and some common additions.
            # This pattern is more restrictive than [^\s]+ but attempts to be robust.
            # It explicitly allows common URL characters, plus characters often found in VLESS/VMESS tags/SNI.
            # It still stops at whitespace, quotes, angle brackets.
            url_chars_pattern = r"[a-zA-Z0-9\-\._~:/?#\[\]@!$&'()*+,;%=\u0600-\u06FF]+"
            
            full_patterns_list.append(r"(?:" + re.escape(prefix) + url_chars_pattern + r")")

    # Special handling for "ssh" if it needs alternative prefixes like "sftp://".
    if "ssh" in settings.ACTIVE_PROTOCOLS and "sftp://" not in [info.get("prefix") for info in active_protocols_info.values()]:
        url_chars_pattern_ssh = r"[a-zA-Z0-9\-\._~:/?#\[\]@!$&'()*+,;%=\u0600-\u06FF]+"
        full_patterns_list.append(r"(?:" + re.escape("sftp://") + url_chars_pattern_ssh + r")")


    combined_full_regex_str = '|'.join(full_patterns_list)
    print(f"protocol_definitions: Generated combined FULL regex string: {combined_full_regex_str}")

    if not combined_full_regex_str:
        print("protocol_definitions: WARNING: No active protocols found to build combined FULL regex. Returning empty match regex.")
        return re.compile(r'a^')

    return re.compile(combined_full_regex_str, re.IGNORECASE)