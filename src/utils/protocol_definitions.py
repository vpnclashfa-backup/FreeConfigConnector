# src/utils/protocol_definitions.py

import re
from typing import Dict, List
from src.utils.settings_manager import settings

# Define base regex patterns for various VPN/proxy protocols.
# These patterns now capture anything *after* the protocol prefix until a whitespace or end of line.
# This makes extraction more permissive. Validation will happen in ConfigValidator.
# The goal here is to NOT miss any potential config due to complex characters within the link itself.
PROTOCOL_REGEX_MAP: Dict[str, str] = {
    # Revised strategy: match the protocol prefix, then any characters until a SPACE or NEWLINE.
    # This will simplify splitting. Further cleaning will occur in ConfigValidator.

    "http": r"https?:\/\/[^\s]+",
    "socks5": r"socks5:\/\/[^\s]+",
    "ss": r"ss:\/\/[^\s]+", # Capture anything after ss:// until space
    "ssr": r"ssr:\/\/[^\s]+", # Capture anything after ssr:// until space
    "vmess": r"vmess:\/\/[^\s]+", # Capture anything after vmess:// until space
    "vless": r"vless:\/\/[^\s]+", # Capture anything after vless:// until space
    "trojan": r"trojan:\/\/[^\s]+",
    "hysteria": r"hysteria:\/\/[^\s]+",
    "hysteria2": r"hy2:\/\/[^\s]+", # Hysteria2 often uses hy2://
    "tuic": r"tuic:\/\/[^\s]+",
    "wireguard": r"wireguard:\/\/[^\s]+",
    "ssh": r"(?:ssh|sftp):\/\/[^\s]+",
    "warp": r"warp:\/\/[^\s]+", # Warp might have complex parts, capture till space
    "juicity": r"juicity:\/\/[^\s]+",
    "mieru": r"mieru:\/\/[^\s]+",
    "snell": r"snell:\/\/[^\s]+",
    "anytls": r"anytls:\/\/[^\s]+",
}

def get_protocol_regex_patterns() -> Dict[str, str]:
    """
    برمی‌گرداند نقشه‌ای از پروتکل‌های فعال به الگوهای RegEx مربوطه.
    این تابع الگوهای RegEx را بر اساس پروتکل‌های فعال در settings.ACTIVE_PROTOCOLS فیلتر می‌کند.
    """
    patterns: Dict[str, str] = {}
    
    for protocol in settings.ACTIVE_PROTOCOLS:
        if protocol in PROTOCOL_REGEX_MAP:
            patterns[protocol] = PROTOCOL_REGEX_MAP[protocol]
        else:
            # Fallback: Capture anything until whitespace or end of string
            patterns[protocol] = re.escape(protocol) + r":\/\/[^\s]+"
    return patterns

def get_combined_protocol_regex() -> re.Pattern:
    """
    برمی‌گرداند یک الگوی RegEx کامپایل شده که می‌تواند شروع هر پروتکل فعال را تشخیص دهد.
    این برای تقسیم متن‌های طولانی به قطعات کانفیگ‌مانند استفاده می‌شود.
    """
    active_patterns_map = get_protocol_regex_patterns()
    # Create a regex that matches the *start* of any active protocol (e.g., 'vless://', 'ss://')
    protocol_prefixes = [re.escape(p_name) + r'\:\/\/' for p_name in active_patterns_map.keys()]
    
    combined_prefix_regex_str = '|'.join(protocol_prefixes)

    if not combined_prefix_regex_str:
        return re.compile(r'a^') # Matches nothing if no protocols are active
    
    return re.compile(combined_prefix_regex_str, re.IGNORECASE)

