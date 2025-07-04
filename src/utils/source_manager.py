import os
import json
from src.utils.settings_manager import settings
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
import re
from urllib.parse import urlparse, parse_qs # Added for parsing MTProto links

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

        print(f"SourceManager: Loaded {len(self.telegram_channels)} initial Telegram channels and {len(self.websites)} initial websites.")
        print(f"SourceManager: Loaded {len(self.timeout_telegram_channels)} previously timed out Telegram channels and {len(self.timeout_websites)} previously timed out websites.")

        self._recover_timed_out_sources()
        print(f"SourceManager: After recovery, {len(self.telegram_channels)} active Telegram channels and {len(self.websites)} active websites.")


    def _load_sources_from_file(self, file_path: str) -> Set[str]:
        """Loads sources (channels/websites) from a plain text file."""
        if not os.path.exists(file_path):
            print(f"SourceManager: Warning: Source file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                pass
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            sources = {line.strip() for line in f if line.strip()}
            print(f"SourceManager: Loaded {len(sources)} sources from {file_path}.")
            return sources

    def _save_sources_to_file(self, sources_set: Set[str], file_path: str):
        """Saves sources (channels/websites) to a plain text file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            for source in sorted(list(sources_set)):
                f.write(source + '\n')
            print(f"SourceManager: Saved {len(sources_set)} sources to {file_path}.")


    def _load_timeout_sources(self, file_path: str) -> Dict[str, Dict[str, str]]:
        """Loads timeout sources from a JSON file, including scores and last timeout time."""
        if not os.path.exists(file_path):
            print(f"SourceManager: Warning: Timeout file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"SourceManager: Loaded {len(data)} timeout sources from {file_path}.")
                return data
        except json.JSONDecodeError as e:
            print(f"SourceManager: ERROR: Invalid JSON format in timeout file {file_path}: {e}. Returning empty.")
            return {}
        except Exception as e:
            print(f"SourceManager: ERROR: An unexpected error occurred while loading timeout file {file_path}: {e}. Returning empty.")
            traceback.print_exc()
            return {}

    def _save_timeout_sources(self, timeout_dict: Dict[str, Dict[str, str]], file_path: str):
        """Saves timeout sources to a JSON file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(timeout_dict, f, indent=4, ensure_ascii=False)
            print(f"SourceManager: Saved {len(timeout_dict)} timeout sources to {file_path}.")


    def _recover_timed_out_sources(self):
        """Attempts to recover sources from timeout lists if enough time has passed."""
        now = datetime.now(timezone.utc)
        print("SourceManager: Attempting to recover timed out sources.")

        channels_to_recover: List[str] = []
        for channel, data in list(self.timeout_telegram_channels.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                channels_to_recover.append(channel)
                print(f"SourceManager: Recovering Telegram channel from timeout (duration passed): {channel}")
        for channel in channels_to_recover:
            self.telegram_channels.add(channel)
            del self.timeout_telegram_channels[channel]

        websites_to_recover: List[str] = []
        for website, data in list(self.timeout_websites.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                websites_to_recover.append(website)
                print(f"SourceManager: Recovering website from timeout (duration passed): {website}")
        for website in websites_to_recover:
            self.websites.add(website)
            del self.timeout_websites[website]
        print(f"SourceManager: Finished recovery. Recovered {len(channels_to_recover)} channels and {len(websites_to_recover)} websites.")


    def add_telegram_channel(self, channel_username: str) -> bool:
        """
        Adds a new Telegram channel to the list of active channels,
        applying advanced filtering.
        """
        standardized_channel = self._standardize_channel_username(channel_username)
        if not standardized_channel:
            print(f"SourceManager: Channel '{channel_username}' failed standardization or was filtered by basic rules (e.g., bot, too short, irrelevant name). Not adding.")
            return False

        # RE-ENABLED: Advanced filtering for Telegram channels
        if self._should_ignore_telegram_channel(standardized_channel):
            print(f"SourceManager: Ignoring Telegram channel '{standardized_channel}' based on advanced filtering rules. Not adding.")
            return False

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
        # RE-ENABLED: Advanced filtering for websites
        if self._should_ignore_website_url(url):
            print(f"SourceManager: Ignoring website URL '{url}' based on advanced filtering rules. Not adding.")
            return False

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

    def update_telegram_channel_score(self, channel_username: str, score_change: int):
        """Updates the score of a Telegram channel and potentially moves it to timeout."""
        if channel_username in self._all_telegram_scores:
            old_score = self._all_telegram_scores[channel_username]
            self._all_telegram_scores[channel_username] += score_change
            print(f"SourceManager: Score for '{channel_username}' updated from {old_score} to {self._all_telegram_scores[channel_username]}. Change: {score_change}.")
            
            if self._all_telegram_scores[channel_username] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
               channel_username not in self.timeout_telegram_channels:
                self._move_telegram_to_timeout(channel_username, self._all_telegram_scores[channel_username])
            elif self._all_telegram_scores[channel_username] > settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
                 channel_username in self.timeout_telegram_channels: # If it's recovered manually or score improved significantly
                print(f"SourceManager: Channel '{channel_username}' has improved score ({self._all_telegram_scores[channel_username]}) and is no longer at timeout threshold. Removing from timeout list if present.")
                self.telegram_channels.add(channel_username)
                self.timeout_telegram_channels.pop(channel_username, None)

        else:
            print(f"SourceManager: WARNING: Attempted to update score for unknown Telegram channel '{channel_username}'. Initializing with score {score_change}.")
            self._all_telegram_scores[channel_username] = score_change
            if self._all_telegram_scores[channel_name] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM:
                 self._move_telegram_to_timeout(channel_username, self._all_telegram_scores[channel_username])


    def update_website_score(self, url: str, score_change: int):
        """Updates the score of a website and potentially moves it to timeout."""
        if url in self._all_website_scores:
            old_score = self._all_website_scores[url]
            self._all_website_scores[url] += score_change
            print(f"SourceManager: Score for '{url}' updated from {old_score} to {self._all_website_scores[url]}. Change: {score_change}.")

            if self._all_website_scores[url] <= settings.MAX_TIMEOUT_SCORE_WEB and \
               url not in self.timeout_websites:
                self._move_website_to_timeout(url, self._all_website_scores[url])
            elif self._all_website_scores[url] > settings.MAX_TIMEOUT_SCORE_WEB and \
                 url in self.timeout_websites: # If it's recovered manually or score improved significantly
                print(f"SourceManager: Website '{url}' has improved score ({self._all_website_scores[url]}) and is no longer at timeout threshold. Removing from timeout list if present.")
                self.websites.add(url)
                self.timeout_websites.pop(url, None)
        else:
            print(f"SourceManager: WARNING: Attempted to update score for unknown website '{url}'. Initializing with score {score_change}.")
            self._all_website_scores[url] = score_change
            if self._all_website_scores[url] <= settings.MAX_TIMEOUT_SCORE_WEB:
                self._move_website_to_timeout(url, self._all_website_scores[url])


    def _move_telegram_to_timeout(self, channel_username: str, score: int):
        """Moves a Telegram channel from active to timeout list."""
        print(f"SourceManager: Channel '{channel_username}' reached timeout score ({score}). Moving to timeout list.")
        self.telegram_channels.discard(channel_username)
        self.timeout_telegram_channels[channel_username] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}


    def _move_website_to_timeout(self, url: str, score: int):
        """Moves a website from active to timeout list."""
        print(f"SourceManager: Website '{url}' reached timeout score ({score}). Moving to timeout list.")
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
            # else:
                # print(f"SourceManager: Channel '{channel}' is NOT eligible (blacklisted, timed out, or not whitelisted).")

        sorted_channels = sorted(eligible_channels, key=lambda ch: self._all_telegram_scores.get(ch, 0), reverse=True)
        print(f"SourceManager: Returning {len(sorted_channels)} active Telegram channels.")
        return sorted_channels

    def get_active_websites(self) -> List[str]:
        """Returns websites that are active, not blacklisted, not currently timed out, and optionally whitelisted, sorted by score (highest first)."""
        eligible_websites: List[str] = []
        for website in self.websites:
            if not self._is_blacklisted_website(website) and \
               not self._is_timed_out_website(website) and \
               self._is_whitelisted_website(website):
                eligible_websites.append(website)
            # else:
                # print(f"SourceManager: Website '{website}' is NOT eligible (blacklisted, timed out, or not whitelisted).")

        sorted_websites = sorted(eligible_websites, key=lambda w: self._all_website_scores.get(w, 0), reverse=True)
        print(f"SourceManager: Returning {len(sorted_websites)} active websites.")
        return sorted_websites

    def get_timed_out_telegram_channels(self) -> List[Dict]:
        """Returns a list of Telegram channels currently in timeout state, sorted by score (highest first, i.e., least negative)."""
        timeout_list: List[Dict] = []
        for channel, data in self.timeout_telegram_channels.items():
            timeout_list.append({"channel": channel, "score": data.get("score", 0), "last_timeout": data.get("last_timeout")})

        # Sort by score in descending order (highest score first, which means least negative)
        return sorted(timeout_list, key=lambda item: item["score"], reverse=True)

    def get_timed_out_websites(self) -> List[Dict]:
        """Returns a list of websites currently in timeout state, sorted by score (highest first, i.e., least negative)."""
        timeout_list: List[Dict] = []
        for website, data in self.timeout_websites.items():
            timeout_list.append({"website": website, "score": data.get("score", 0), "last_timeout": data.get("last_timeout")})

        # Sort by score in descending order (highest score first, which means least negative)
        return sorted(timeout_list, key=lambda item: item["score"], reverse=True)


    def _is_blacklisted_telegram_channel(self, channel_username: str) -> bool:
        is_blacklisted = channel_username in settings.BLACKLIST_TELEGRAM_CHANNELS
        if is_blacklisted: print(f"SourceManager: Channel '{channel_username}' is explicitly blacklisted.")
        return is_blacklisted

    def _is_blacklisted_website(self, url: str) -> bool:
        is_blacklisted = url in settings.BLACKLIST_WEBSITES
        if is_blacklisted: print(f"SourceManager: Website '{url}' is explicitly blacklisted.")
        return is_blacklisted

    def _is_whitelisted_telegram_channel(self, channel_username: str) -> bool:
        is_whitelisted = not settings.WHITELIST_TELEGRAM_CHANNELS or channel_username in settings.WHITELIST_TELEGRAM_CHANNELS
        return is_whitelisted

    def _is_whitelisted_website(self, url: str) -> bool:
        is_whitelisted = not settings.WHITELIST_WEBSITES or url in settings.WHITELIST_WEBSITES
        return is_whitelisted


    def _is_timed_out_telegram_channel(self, channel_username: str) -> bool:
        """Checks if a Telegram channel is in timeout and if it should recover."""
        if channel_username in self.timeout_telegram_channels:
            last_timeout_str = self.timeout_telegram_channels[channel_username].get("last_timeout")
            if last_timeout_str:
                last_timeout_dt = datetime.fromisoformat(last_timeout_str)
                is_timed_out_still = datetime.now(timezone.utc) - last_timeout_dt < settings.TIMEOUT_RECOVERY_DURATION
                if is_timed_out_still:
                    print(f"SourceManager: Channel '{channel_username}' is still timed out. Will recover in {(settings.TIMEOUT_RECOVERY_DURATION - (datetime.now(timezone.utc) - last_timeout_dt)).total_seconds() / 86400:.2f} days.")
                return is_timed_out_still
        return False

    def _is_timed_out_website(self, url: str) -> bool:
        """Checks if a website is in timeout and if it should recover."""
        if url in self.timeout_websites:
            last_timeout_str = self.timeout_websites[url].get("last_timeout")
            if last_timeout_str:
                last_timeout_dt = datetime.fromisoformat(last_timeout_str)
                is_timed_out_still = datetime.now(timezone.utc) - last_timeout_dt < settings.TIMEOUT_