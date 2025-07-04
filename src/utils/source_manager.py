import os
import json
from src.utils.settings_manager import settings
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
import re

class SourceManager:
    # ... (کدهای موجود __init__, _load_sources_from_file, _save_sources_to_file, _load_timeout_sources, _save_timeout_sources, _recover_timed_out_sources)

    def add_telegram_channel(self, channel_username: str) -> bool:
        """
        Adds a new Telegram channel to the list of active channels,
        applying advanced filtering.
        """
        standardized_channel = self._standardize_channel_username(channel_username)
        if not standardized_channel:
            print(f"SourceManager: Channel '{channel_username}' failed standardization or was filtered by basic rules (e.g., bot, too short, irrelevant name). Not adding.")
            return False

        # --- RE-ENABLED: Advanced filtering for Telegram channels ---
        if self._should_ignore_telegram_channel(standardized_channel):
            print(f"SourceManager: Ignoring Telegram channel '{standardized_channel}' based on advanced filtering rules. Not adding.")
            return False
        # --- END RE-ENABLED BLOCK ---

        if standardized_channel in self.telegram_channels:
            return False
        
        if standardized_channel in self.timeout_telegram_channels:
            print(f"SourceManager: Channel '{standardized_channel}' is currently timed out. Not adding to active list.")
            return False

        if self._is_blacklisted_telegram_channel(standardized_channel):
            print(f"SourceManager: Channel '{standardized_channel}' is blacklisted. Not adding.")
            return False

        if settings.WHITELIST_TELEGRAM_CHANNELS and standardized_channel not in settings.WHITELIST_TELEGRAM_CHANNELS:
            print(f"SourceManager: Skipping discovered channel {standardized_channel} as it's not in whitelist and whitelist is active. Not adding.")
            return False

        if len(self.telegram_channels) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.telegram_channels.add(standardized_channel)
            self._all_telegram_scores[standardized_channel] = 0
            print(f"SourceManager: ADDED new Telegram channel '{standardized_channel}' to active list.")
            return True
        else:
            print(f"SourceManager: Max discovered Telegram channels limit ({settings.MAX_DISCOVERED_SOURCES_TO_ADD}) reached. Skipping '{standardized_channel}'.")
        return False

    def add_website(self, url: str) -> bool:
        """
        Adds a new website URL to the list of active websites.
        Advanced filtering is RE-ENABLED.
        """
        # --- RE-ENABLED: Advanced filtering for websites ---
        if self._should_ignore_website_url(url):
            print(f"SourceManager: Ignoring website URL '{url}' based on advanced filtering rules. Not adding.")
            return False
        # --- END RE-ENABLED BLOCK ---

        if url in self.websites:
            return False
        
        if url in self.timeout_websites:
            print(f"SourceManager: Website '{url}' is currently timed out. Not adding to active list.")
            return False

        if self._is_blacklisted_website(url):
            print(f"SourceManager: Website '{url}' is blacklisted. Not adding.")
            return False

        if settings.WHITELIST_WEBSITES and url not in settings.WHITELIST_WEBSITES:
            print(f"SourceManager: Skipping discovered website {url} as it's not in whitelist and whitelist is active. Not adding.")
            return False

        if len(self.websites) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.websites.add(url)
            self._all_website_scores[url] = 0
            print(f"SourceManager: ADDED new website URL '{url}' to active list.")
            return True
        else:
            print(f"SourceManager: Max discovered websites limit ({settings.MAX_DISCOVERED_SOURCES_TO_ADD}) reached. Skipping '{url}'.")
        return False

    # ... (بقیه کدهای موجود تا انتهای فایل)

    # --- NEW: Advanced Filtering Logic (که الان از کامنت خارج شده) ---
    def _should_ignore_telegram_channel(self, channel_username: str) -> bool:
        """
        Checks if a Telegram channel should be ignored based on its name.
        """
        username_lower = channel_username.lower().lstrip('@')
        
        if username_lower in ['proxy', 'img', 'emoji', 'joinchat', 's', '']:
            print(f"SourceManager: Ignoring Telegram channel '{channel_username}' (common irrelevant name in _should_ignore).")
            return True
        
        mtproto_like_pattern = re.compile(r'^(?:proxyserver|proxy|mtproto|server|config)[a-zA-Z0-9]{5,}', re.IGNORECASE)
        long_random_looking_pattern = re.compile(r'.*[a-zA-Z0-9]{10,}(?:ampport|secret|media)\b.*', re.IGNORECASE)

        if mtproto_like_pattern.search(username_lower) or long_random_looking_pattern.search(username_lower):
            print(f"SourceManager: Ignoring Telegram channel '{channel_username}' (looks like an MTProto proxy link or random string).")
            return True

        return False

    def _should_ignore_website_url(self, url: str) -> bool:
        """
        Checks if a website URL should be ignored based on its content or domain.
        """
        url_lower = url.lower()
        
        accept_keywords = ['sub', 'subscribe', 'token', 'workers', 'worker', 'dev', 'txt', 'vmess', 'vless', 'reality', 'trojan', 'shadowsocks', 'hy', 'tuic', 'juicity', 'configs']
        
        avoid_domains_and_keywords = ['github.com', 'raw.githubusercontent.com', 'gist.github.com', 'git.io', 
                                      'google.com', 'play.google.com', 'apple.com', 'microsoft.com', 
                                      'gitlab.com', 'bitbucket.org', 'docs.google.com', 
                                      'drive.google.com', 't.me']

        if not any(kw in url_lower for kw in accept_keywords):
            print(f"SourceManager: Ignoring website URL '{url}' (no relevant keywords found in URL).")
            return True
        
        if any(dom in url_lower for dom in avoid_domains_and_keywords):
            print(f"SourceManager: Ignoring website URL '{url}' (contains avoided domain/keyword).")
            return True

        return False

# Create a global instance of SourceManager
source_manager = SourceManager()