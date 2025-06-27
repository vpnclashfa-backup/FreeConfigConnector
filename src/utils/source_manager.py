# src/utils/source_manager.py

import os
import json
from src.utils.settings_manager import settings
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set # NEW: Import List, Dict, Optional, Set

class SourceManager:
    def __init__(self):
        self.telegram_channels: Set[str] = self._load_sources_from_file(settings.CHANNELS_FILE)
        self.websites: Set[str] = self._load_sources_from_file(settings.WEBSITES_FILE)
        
        self.timeout_telegram_channels: Dict[str, Dict[str, str]] = self._load_timeout_sources(settings.TIMEOUT_TELEGRAM_CHANNELS_FILE)
        self.timeout_websites: Dict[str, Dict[str, str]] = self._load_timeout_sources(settings.TIMEOUT_WEBSITES_FILE)

        self._all_telegram_scores: Dict[str, int] = {}
        for s in self.telegram_channels:
            self._all_telegram_scores[s] = self.timeout_telegram_channels.get(s, {}).get("score", 0)
        for s, data in self.timeout_telegram_channels.items():
            if s not in self._all_telegram_scores:
                self._all_telegram_scores[s] = data.get("score", 0)

        self._all_website_scores: Dict[str, int] = {}
        for s in self.websites:
            self._all_website_scores[s] = self.timeout_websites.get(s, {}).get("score", 0)
        for s, data in self.timeout_websites.items():
            if s not in self._all_website_scores:
                self._all_website_scores[s] = data.get("score", 0)
        
        print(f"Loaded {len(self.telegram_channels)} initial Telegram channels and {len(self.websites)} initial websites.")
        print(f"Loaded {len(self.timeout_telegram_channels)} previously timed out Telegram channels and {len(self.timeout_websites)} previously timed out websites.")
        
        self._recover_timed_out_sources()

    def _load_sources_from_file(self, file_path: str) -> Set[str]:
        """Loads sources (channels/websites) from a plain text file."""
        if not os.path.exists(file_path):
            print(f"Warning: Source file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                pass
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            return {line.strip() for line in f if line.strip()}

    def _save_sources_to_file(self, sources_set: Set[str], file_path: str):
        """Saves sources (channels/websites) to a plain text file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            for source in sorted(list(sources_set)):
                f.write(source + '\n')

    def _load_timeout_sources(self, file_path: str) -> Dict[str, Dict[str, str]]:
        """Loads timeout sources from a JSON file, including scores and last timeout time."""
        if not os.path.exists(file_path):
            print(f"Warning: Timeout file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except json.JSONDecodeError as e:
            print(f"Error reading timeout file {file_path}: Invalid JSON format. {e}")
            return {}
        except Exception as e:
            print(f"An unexpected error occurred while loading timeout file {file_path}: {e}")
            return {}

    def _save_timeout_sources(self, timeout_dict: Dict[str, Dict[str, str]], file_path: str):
        """Saves timeout sources to a JSON file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(timeout_dict, f, indent=4, ensure_ascii=False)

    def _recover_timed_out_sources(self):
        """Attempts to recover sources from timeout lists if enough time has passed."""
        now = datetime.now(timezone.utc)
        
        channels_to_recover: List[str] = []
        for channel, data in list(self.timeout_telegram_channels.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                channels_to_recover.append(channel)
                print(f"Recovering Telegram channel from timeout: {channel}")
        for channel in channels_to_recover:
            self.telegram_channels.add(channel)
            del self.timeout_telegram_channels[channel]

        websites_to_recover: List[str] = []
        for website, data in list(self.timeout_websites.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                websites_to_recover.append(website)
                print(f"Recovering website from timeout: {website}")
        for website in websites_to_recover:
            self.websites.add(website)
            del self.timeout_websites[website]

    def add_telegram_channel(self, channel_username: str) -> bool:
        """Adds a new Telegram channel to the list of active channels."""
        standardized_channel = self._standardize_channel_username(channel_username)
        if not standardized_channel:
            return False

        if standardized_channel in self.telegram_channels or \
           standardized_channel in self.timeout_telegram_channels or \
           self._is_blacklisted_telegram_channel(standardized_channel):
            return False
        
        if settings.WHITELIST_TELEGRAM_CHANNELS and standardized_channel not in settings.WHITELIST_TELEGRAM_CHANNELS:
            print(f"Skipping discovered channel {standardized_channel} as it's not in whitelist.")
            return False

        if len(self.telegram_channels) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.telegram_channels.add(standardized_channel)
            self._all_telegram_scores[standardized_channel] = 0
            print(f"Added new Telegram channel to active list: {standardized_channel}")
            return True
        else:
            print(f"Max discovered Telegram channels limit reached. Skipping {standardized_channel}")
        return False

    def add_website(self, url: str) -> bool:
        """Adds a new website URL to the list of active websites."""
        if url in self.websites or \
           url in self.timeout_websites or \
           self._is_blacklisted_website(url):
            return False
        
        if settings.WHITELIST_WEBSITES and url not in settings.WHITELIST_WEBSITES:
            print(f"Skipping discovered website {url} as it's not in whitelist.")
            return False

        if len(self.websites) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.websites.add(url)
            self._all_website_scores[url] = 0
            print(f"Added new website to active list: {url}")
            return True
        else:
            print(f"Max discovered websites limit reached. Skipping {url}")
        return False

    def update_telegram_channel_score(self, channel_username: str, score_change: int):
        """Updates the score of a Telegram channel and potentially moves it to timeout."""
        if channel_username in self._all_telegram_scores:
            self._all_telegram_scores[channel_username] += score_change
            print(f"Score for {channel_username} updated to {self._all_telegram_scores[channel_username]}")
            
            if self._all_telegram_scores[channel_username] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
               channel_username not in self.timeout_telegram_channels:
                self._move_telegram_to_timeout(channel_username, self._all_telegram_scores[channel_username])

    def update_website_score(self, url: str, score_change: int):
        """Updates the score of a website and potentially moves it to timeout."""
        if url in self._all_website_scores:
            self._all_website_scores[url] += score_change
            print(f"Score for {url} updated to {self._all_website_scores[url]}")
            
            if self._all_website_scores[url] <= settings.MAX_TIMEOUT_SCORE_WEB and \
               url not in self.timeout_websites:
                self._move_website_to_timeout(url, self._all_website_scores[url])

    def _move_telegram_to_timeout(self, channel_username: str, score: int):
        """Moves a Telegram channel from active to timeout list."""
        print(f"Channel {channel_username} reached timeout score ({score}). Moving to timeout list.")
        self.telegram_channels.discard(channel_username)
        self.timeout_telegram_channels[channel_username] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}

    def _move_website_to_timeout(self, url: str, score: int):
        """Moves a website from active to timeout list."""
        print(f"Website {url} reached timeout score ({score}). Moving to timeout list.")
        self.websites.discard(url)
        self.timeout_websites[url] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}

    def get_active_telegram_channels(self) -> List[str]:
        """Returns Telegram channels that are active, not blacklisted, not currently timed out, and optionally whitelisted, sorted by score (highest first)."""
        
        eligible_channels: List[str] = []
        for channel in self.telegram_channels:
            if not self._is_blacklisted_telegram_channel(channel) and \
               not self._is_timed_out_telegram_channel(channel) and \
               self._is_whitelisted_telegram_channel(channel):
                eligible_channels.append(channel)
        
        sorted_channels = sorted(eligible_channels, key=lambda ch: self._all_telegram_scores.get(ch, 0), reverse=True)
        return sorted_channels

    def get_active_websites(self) -> List[str]:
        """Returns websites that are active, not blacklisted, not currently timed out, and optionally whitelisted, sorted by score (highest first)."""
        eligible_websites: List[str] = []
        for website in self.websites:
            if not self._is_blacklisted_website(website) and \
               not self._is_timed_out_website(website) and \
               self._is_whitelisted_website(website):
                eligible_websites.append(website)
        
        sorted_websites = sorted(eligible_websites, key=lambda w: self._all_website_scores.get(w, 0), reverse=True)
        return sorted_websites

    def get_timed_out_telegram_channels(self) -> List[Dict]:
        """Returns a list of Telegram channels currently in timeout state, sorted by score (lowest first)."""
        timeout_list: List[Dict] = [] # Use Dict to hold channel and score
        for channel, data in self.timeout_telegram_channels.items():
            timeout_list.append({"channel": channel, "score": data.get("score", 0), "last_timeout": data.get("last_timeout")})
        
        return sorted(timeout_list, key=lambda item: item["score"])

    def get_timed_out_websites(self) -> List[Dict]:
        """Returns a list of websites currently in timeout state, sorted by score (lowest first)."""
        timeout_list: List[Dict] = []
        for website, data in self.timeout_websites.items():
            timeout_list.append({"website": website, "score": data.get("score", 0), "last_timeout": data.get("last_timeout")})
        
        return sorted(timeout_list, key=lambda item: item["score"])


    def _is_blacklisted_telegram_channel(self, channel_username: str) -> bool:
        return channel_username in settings.BLACKLIST_TELEGRAM_CHANNELS

    def _is_blacklisted_website(self, url: str) -> bool:
        return url in settings.BLACKLIST_WEBSITES

    def _is_whitelisted_telegram_channel(self, channel_username: str) -> bool:
        return not settings.WHITELIST_TELEGRAM_CHANNELS or channel_username in settings.WHITELIST_TELEGRAM_CHANNELS

    def _is_whitelisted_website(self, url: str) -> bool:
        return not settings.WHITELIST_WEBSITES or url in settings.WHITELIST_WEBSITES

    def _is_timed_out_telegram_channel(self, channel_username: str) -> bool:
        """Checks if a Telegram channel is in timeout and if it should recover."""
        if channel_username in self.timeout_telegram_channels:
            last_timeout_str = self.timeout_telegram_channels[channel_username].get("last_timeout")
            if last_timeout_str:
                last_timeout_dt = datetime.fromisoformat(last_timeout_str)
                return datetime.now(timezone.utc) - last_timeout_dt < settings.TIMEOUT_RECOVERY_DURATION
        return False

    def _is_timed_out_website(self, url: str) -> bool:
        """Checks if a website is in timeout and if it should recover."""
        if url in self.timeout_websites:
            last_timeout_str = self.timeout_websites[url].get("last_timeout")
            if last_timeout_str:
                last_timeout_dt = datetime.fromisoformat(last_timeout_str)
                return datetime.now(timezone.utc) - last_timeout_dt < settings.TIMEOUT_RECOVERY_DURATION
        return False

    def finalize(self):
        """Saves all current source lists and timeout lists to files."""
        print("Saving source manager state...")
        self._save_sources_to_file(self.telegram_channels, settings.CHANNELS_FILE)
        self._save_sources_to_file(self.websites, settings.WEBSITES_FILE)
        
        for channel, score in self._all_telegram_scores.items():
            self.timeout_telegram_channels[channel] = {"score": score, "last_timeout": self.timeout_telegram_channels.get(channel, {}).get("last_timeout", datetime.now(timezone.utc).isoformat())}
        for website, score in self._all_website_scores.items():
            self.timeout_websites[website] = {"score": score, "last_timeout": self.timeout_websites.get(website, {}).get("last_timeout", datetime.now(timezone.utc).isoformat())}

        self._save_timeout_sources(self.timeout_telegram_channels, settings.TIMEOUT_TELEGRAM_CHANNELS_FILE)
        self._save_timeout_sources(self.timeout_websites, settings.TIMEOUT_WEBSITES_FILE)
        print("Source manager state saved.")

    def _standardize_channel_username(self, raw_input: str) -> Optional[str]:
        username = raw_input.replace('https://t.me/s/', '').replace('https://t.me/', '').replace('t.me/s/', '').replace('t.me/', '')
        if username.endswith('@'):
            username = username[:-1]
        if username.lower().endswith("bot"):
            return None
        if not username.startswith('@'):
            username = '@' + username
        return username.strip()

# ایجاد یک نمونه سراسری از SourceManager
source_manager = SourceManager()
