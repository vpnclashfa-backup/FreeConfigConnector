# src/utils/protocol_definitions.py

import re
from typing import Dict, List
from src.utils.settings_manager import settings

# Define base regex patterns for various VPN/proxy protocols.
# These patterns aim to capture the FULL config link including path, query, and fragment (#title).
# They are designed to be permissive and capture as much as possible until a clear break.
PROTOCOL_REGEX_MAP: Dict[str, str] = {
    # Common pattern: protocol://[userinfo@]host:port[/path][?query][#fragment]
    # [^\s]+ is generally too broad, [^\s#]+ is better for fragment.
    # However, some parts can contain '/', '?', '#', '=', '&', '%' if URL-encoded or part of data.
    # So, we aim to match until a clear "non-link" character or the beginning of another link.
    # We use (?:[^#\s]+)? for fragment as it can contain anything.
    # (?:[^#\s]*) is more general for fragment.

    # HTTP/SOCKS5: simple URLs
    "http": r"https?:\/\/[a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]+", # More robust URL chars
    "socks5": r"socks5:\/\/[a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]+",

    # SS: ss://base64(method:password)[@host:port][#title]
    # Base64 part can contain '+/=' and URL-encoded chars. Host/port/title can have more.
    "ss": r"ss:\/\/[A-Za-z0-9+/=_-]+(?:@[a-zA-Z0-9.\-_~%]+:[0-9]+)?(?:#.+)?",
    
    # SSR: ssr://base64_url(JSON_payload)#title
    "ssr": r"ssr:\/\/[A-Za-z0-9+/=_-]+(?:#.+)?", 

    # Vmess: vmess://base64(JSON_config)#[title]
    "vmess": r"vmess:\/\/[A-Za-z0-9+/=_-]+(?:#.+)?",
    
    # Vless: vless://uuid@host:port[?query][#title]
    # Query parameters can be complex.
    "vless": r"vless:\/\/[a-zA-Z0-9\-]+@[a-zA-Z0-9.\-_~%]+:[0-9]+(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # Trojan: trojan://password@host:port[?query][#title]
    "trojan": r"trojan:\/\/[a-zA-Z0-9.\-_~%]+@[a-zA-Z0-9.\-_~%]+:[0-9]+(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # Hysteria: hysteria://host:port[?query][#title]
    "hysteria": r"hysteria:\/\/[a-zA-Z0-9.\-_~%]+:[0-9]+(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # Hysteria2: hy2://password@host:port[?query][#title] (often starts with hy2://)
    "hysteria2": r"hy2:\/\/[a-zA-Z0-9.\-_~%]+@[a-zA-Z0-9.\-_~%]+:[0-9]+(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # TUIC: tuic://uuid:password@host:port[?query][#title]
    "tuic": r"tuic:\/\/[a-zA-Z0-9\-]+:[a-zA-Z0-9.\-_~%]+@[a-zA-Z0-9.\-_~%]+:[0-9]+(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # WireGuard: wireguard://[base64_public_key]@host:port[?query][#title]
    "wireguard": r"wireguard:\/\/[A-Za-z0-9+/=_-]+(?:@[a-zA-Z0-9.\-_~%]+:[0-9]+)?(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # SSH: ssh://user:pass@host:port[#title] or sftp://
    "ssh": r"(?:ssh|sftp):\/\/[a-zA-Z0-9.\-_~%]+(?:@[a-zA-Z0-9.\-_~%]+:[0-9]+)?(?:#.+)?",
    
    # Warp: warp://[id@]host:port[?query][#title] - often simple
    "warp": r"warp:\/\/[a-zA-Z0-9.\-_~%]+(?:@[a-zA-Z0-9.\-_~%]+:[0-9]+)?(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    # Juicity: juicity://UUID:password@host:port[?query][#title]
    "juicity": r"juicity:\/\/[a-zA-Z0-9\-]+:[a-zA-Z0-9.\-_~%]+@[a-zA-Z0-9.\-_~%]+:[0-9]+(?:[\/?#][a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]*)?",
    
    "mieru": r"mieru:\/\/[a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]+",
    "snell": r"snell:\/\/[a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]+",
    "anytls": r"anytls:\/\/[a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]+",
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
            # Fallback to a generic pattern if a specific one isn't defined
            # If a protocol is active but has no specific regex, use a general URL pattern.
            patterns[protocol] = re.escape(protocol) + r":\/\/[a-zA-Z0-9.\-_~:/?#[\]@!$&'()*+,;%=]+"
    return patterns

def get_combined_protocol_regex() -> re.Pattern:
    """
    برمی‌گرداند یک الگوی RegEx کامپایل شده که می‌تواند شروع هر پروتکل فعال را تشخیص دهد.
    این برای تقسیم متن‌های طولانی به قطعات کانفیگ‌مانند استفاده می‌شود.
    """
    active_patterns_map = get_protocol_regex_patterns()
    # Create a regex that matches the start of any active protocol.
    # This is for identifying the beginning of each config string within a larger text block.
    # Example: (vless://|ss://|trojan://)
    
    # We create a list of escaped protocol prefixes (e.g., "vless://", "ss://")
    protocol_prefixes = [re.escape(p + '://') for p in active_patterns_map.keys()]
    
    # Combine them with OR | to create a single regex for finding any start.
    combined_prefix_regex_str = '|'.join(protocol_prefixes)

    if not combined_prefix_regex_str:
        return re.compile(r'a^') # Matches nothing if no protocols are active
    
    return re.compile(combined_prefix_regex_str, re.IGNORECASE)

