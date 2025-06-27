# src/utils/protocol_definitions.py

import re
from typing import Dict, List
from src.utils.settings_manager import settings

# تعریف نقشه‌ای از پروتکل‌ها به الگوهای RegEx پایه آن‌ها
# این الگوها برای یافتن لینک‌های کانفیگ مستقیم در متن استفاده می‌شوند.
# این الگوها باید کل لینک را تا پایان ممکن (قبل از فضای خالی یا #) بگیرند
# و نباید شامل کاراکترهای URL-encoded مثل % باشند (آنها بخشی از لینک هستند)
PROTOCOL_REGEX_MAP: Dict[str, str] = {
    # General URL format: protocol://[userinfo@]host:port[/path][?query][#fragment]
    # We use [^\s#]+ to capture till first space or hash (#), as # is often followed by title.
    # Some protocols might have # within their base64 part, but generally # denotes a title.

    "http": r"https?:\/\/[^\s#]+",
    "socks5": r"socks5:\/\/[^\s#]+",
    # SS: ss://base64(method:password)@host:port#title
    # Base64 part can contain =
    "ss": r"ss:\/\/[A-Za-z0-9+/=_-]+@[^\s#]+", 
    # SSR: Similar to SS, often with /protocol# or /obfs#
    "ssr": r"ssr:\/\/[A-Za-z0-9+/=_-]+@[^\s#]+", 
    # Vmess: vmess://base64(JSON_config)#title
    "vmess": r"vmess:\/\/[A-Za-z0-9+/=_-]+#?[^\s]*", # Vmess has base64 then optional #title
    # Vless: vless://uuid@host:port[?query][#title]
    "vless": r"vless:\/\/[^\s#]+", # Captures until space or #
    # Trojan: trojan://password@host:port[?query][#title]
    "trojan": r"trojan:\/\/[^\s#]+",
    # Reality is a VLESS variant, so its detection is in validator.
    # Reality has complex query params, so [^\s#]+ is good.

    "hysteria": r"hysteria:\/\/[^\s#]+",
    "hysteria2": r"hysteria2:\/\/[^\s#]+",
    "tuic": r"tuic:\/\/[^\s#]+",
    "wireguard": r"wg:\/\/[^\s#]+", # wg configs can be long, but often single line
    "ssh": r"(?:ssh|sftp):\/\/[^\s#]+", # ssh, sftp
    "warp": r"(?:warp|cloudflare-warp):\/\/[^\s#]+", # warp, cloudflare-warp
    "juicity": r"juicity:\/\/[^\s#]+",
    "mieru": r"mieru:\/\/[^\s#]+",
    "snell": r"snell:\/\/[^\s#]+",
    "anytls": r"anytls:\/\/[^\s#]+",
    # 'ssconf://' is handled as a subscription URL, not a config directly for regex extraction here.
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
            patterns[protocol] = re.escape(protocol) + r":\/\/[^\s#]+"
    return patterns

def get_combined_protocol_regex() -> re.Pattern:
    """
    برمی‌گرداند یک الگوی RegEx کامپایل شده که می‌تواند شروع هر پروتکل فعال را تشخیص دهد.
    این برای تقسیم متن‌های طولانی به قطعات کانفیگ‌مانند استفاده می‌شود.
    """
    active_patterns = get_protocol_regex_patterns()
    # Create patterns for protocol prefixes (e.g., 'vless://', 'ss://')
    # Use re.escape to handle special characters in protocol names if any (e.g., 'http')
    # We want to match the *start* of a config, so we use the protocol name followed by ://
    # For some like SSH, it's ssh:// or sftp://, so use the full pattern.
    pattern_strings = [re.escape(p_name) + r'\:\/\/' for p_name in active_patterns.keys()] # e.g. vmess://, ss://

    # Reality detection starts with vless, so it's a special case handled by validator after initial vless match.
    # The combined regex should focus on common valid URL characters.
    # It must be robust to capture the *full* config part before any # or next protocol or junk.
    # The individual patterns in PROTOCOL_REGEX_MAP are designed to capture the whole link.
    
    # Combined regex should just look for the start of any protocol defined in PROTOCOL_REGEX_MAP
    # And then we let split_configs_from_text handle the end.
    
    # Combine only the start prefixes for matching.
    # We explicitly list common prefixes here for robustness, or iterate PROTOCOL_REGEX_MAP.
    # A simple approach: combine all protocol regexes, but ensure they are non-greedy or match up to a clear boundary.
    # The individual patterns from PROTOCOL_REGEX_MAP already match up to a space or #.
    # So, we can just combine all of them.
    
    # We'll use the patterns directly, ensuring they are separated by OR |
    combined_pattern_str = '|'.join(PROTOCOL_REGEX_MAP.values())

    if not combined_pattern_str:
        return re.compile(r'a^') # Matches nothing if no protocols are active
    
    return re.compile(combined_pattern_str, re.IGNORECASE)

