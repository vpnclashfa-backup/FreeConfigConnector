# src/utils/protocol_definitions.py

import re
from typing import Dict, List
from src.utils.settings_manager import settings

# تعریف نقشه‌ای از پروتکل‌ها به الگوهای RegEx پایه آن‌ها
# این الگوها برای یافتن لینک‌های کانفیگ مستقیم در متن استفاده می‌شوند.
PROTOCOL_REGEX_MAP: Dict[str, str] = {
    "http": r"https?:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "socks5": r"socks5:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "ss": r"ss:\/\/[a-zA-Z0-9\+\/=]{20,}(?:@[a-zA-Z0-9\.\-]+:\d{1,5})?(?:#.*)?",
    "ssr": r"ssr:\/\/[a-zA-Z0-9\+\/=]{20,}(?:@[a-zA-Z0-9\.\-]+:\d{1,5})?(?:#.*)?",
    "vmess": r"vmess:\/\/[a-zA-Z0-9\+\/=]+",
    "vless": r"vless:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "trojan": r"trojan:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "reality": r"vless:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+?(?:type=reality&.*?host=[^\s&]+.*?sni=[^\s&]+.*?fingerprint=[^\s&]+.*?)?",
    "hysteria": r"hysteria:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "hysteria2": r"hysteria2:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "tuic": r"tuic:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "wireguard": r"wg:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "ssh": r"(?:ssh|sftp):\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "warp": r"(?:warp|cloudflare-warp):\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "juicity": r"juicity:\/\/" + r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+", # Changed to be consistent with others
    "mieru": r"mieru:\/\/" + r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "snell": r"snell:\/\/" + r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    "anytls": r"anytls:\/\/" + r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+",
    # 'ssconf://' is a special URL scheme, not a config protocol per se, so it's handled differently.
    # We will exclude it from regex matching here if it's meant for fetching files.
}

def get_protocol_regex_patterns() -> Dict[str, str]:
    """
    برمی‌گرداند نقشه‌ای از پروتکل‌های فعال به الگوهای RegEx مربوطه.
    این تابع الگوهای RegEx را بر اساس پروتکل‌های فعال در settings.ACTIVE_PROTOCOLS فیلتر می‌کند.
    """
    patterns: Dict[str, str] = {}
    base_pattern_suffix = r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+" # پیشوند کلی برای ادامه لینک
    
    for protocol in settings.ACTIVE_PROTOCOLS:
        if protocol in PROTOCOL_REGEX_MAP:
            patterns[protocol] = PROTOCOL_REGEX_MAP[protocol]
        else:
            # Fallback to a generic pattern if a specific one isn't defined
            # برای پروتکل‌هایی که الگوی خاصی ندارند، یک الگوی عمومی ایجاد می‌کند
            patterns[protocol] = re.escape(protocol) + r":\/\/" + base_pattern_suffix
    return patterns

def get_combined_protocol_regex() -> re.Pattern:
    """
    برمی‌گرداند یک الگوی RegEx کامپایل شده که می‌تواند شروع هر پروتکل فعال را تشخیص دهد.
    این برای تقسیم متن‌های طولانی به قطعات کانفیگ‌مانند استفاده می‌شود.
    """
    active_patterns = get_protocol_regex_patterns()
    # اطمینان حاصل می‌کند که فقط شروع پروتکل‌ها را می‌گیرد
    pattern_strings = [re.escape(p + '://') for p in active_patterns.keys()]
    
    # برای پروتکل‌هایی مانند 'ssh' که ممکن است 'ssh://' یا 'sftp://' داشته باشند
    # باید مطمئن شد که الگوی صحیح از PROTOCOL_REGEX_MAP گرفته می‌شود
    # یا می‌توانیم فقط پیشوندهای ساده را بگیریم
    
    # بهتر است از پیشوندهای مستقیم (key of PROTOCOL_REGEX_MAP) استفاده کنیم:
    direct_prefixes = [re.escape(k) for k in PROTOCOL_REGEX_MAP.keys()]
    
    # Combie all active protocol patterns for splitting purposes.
    # Exclude special cases like 'ssconf' which might not be used for splitting text.
    combined_pattern_str = '|'.join(
        [PROTOCOL_REGEX_MAP[p] for p in settings.ACTIVE_PROTOCOLS if p in PROTOCOL_REGEX_MAP]
    )

    # If no active protocols, provide a dummy pattern to avoid error, or handle upstream
    if not combined_pattern_str:
        return re.compile(r'a^') # Pattern that matches nothing
    
    return re.compile(combined_pattern_str, re.IGNORECASE)

