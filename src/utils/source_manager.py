import os
import json
from src.utils.settings_manager import settings
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Set
import re # Added for advanced filtering

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
        print(f"SourceManager: After recovery, {len(self.telegram_channels)} active Telegram channels and {len(self.websites)} active websites.") # Log after recovery


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
            print(f"SourceManager: Loaded {len(sources)} sources from {file_path}.") # Log loaded sources
            return sources

    def _save_sources_to_file(self, sources_set: Set[str], file_path: str):
        """Saves sources (channels/websites) to a plain text file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            for source in sorted(list(sources_set)):
                f.write(source + '\n')
            print(f"SourceManager: Saved {len(sources_set)} sources to {file_path}.") # Log saved sources


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
                print(f"SourceManager: Loaded {len(data)} timeout sources from {file_path}.") # Log loaded timeouts
                return data
        except json.JSONDecodeError as e:
            print(f"SourceManager: ERROR: Invalid JSON format in timeout file {file_path}: {e}. Returning empty.") # Error log
            return {}
        except Exception as e:
            print(f"SourceManager: ERROR: An unexpected error occurred while loading timeout file {file_path}: {e}. Returning empty.") # Error log
            traceback.print_exc()
            return {}

    def _save_timeout_sources(self, timeout_dict: Dict[str, Dict[str, str]], file_path: str):
        """Saves timeout sources to a JSON file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(timeout_dict, f, indent=4, ensure_ascii=False)
            print(f"SourceManager: Saved {len(timeout_dict)} timeout sources to {file_path}.") # Log saved timeouts


    def _recover_timed_out_sources(self):
        """Attempts to recover sources from timeout lists if enough time has passed."""
        now = datetime.now(timezone.utc)
        print("SourceManager: Attempting to recover timed out sources.") # Log recovery start

        channels_to_recover: List[str] = []
        for channel, data in list(self.timeout_telegram_channels.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                channels_to_recover.append(channel)
                print(f"SourceManager: Recovering Telegram channel from timeout (duration passed): {channel}") # Log recovery
        for channel in channels_to_recover:
            self.telegram_channels.add(channel)
            del self.timeout_telegram_channels[channel]

        websites_to_recover: List[str] = []
        for website, data in list(self.timeout_websites.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                websites_to_recover.append(website)
                print(f"SourceManager: Recovering website from timeout (duration passed): {website}") # Log recovery
        for website in websites_to_recover:
            self.websites.add(website)
            del self.timeout_websites[website]
        print(f"SourceManager: Finished recovery. Recovered {len(channels_to_recover)} channels and {len(websites_to_recover)} websites.") # Summary log


    def add_telegram_channel(self, channel_username: str) -> bool:
        """
        Adds a new Telegram channel to the list of active channels.
        Advanced filtering is TEMPORARILY DISABLED for debugging.
        """
        standardized_channel = self._standardize_channel_username(channel_username)
        if not standardized_channel:
            print(f"SourceManager: Channel '{channel_username}' failed standardization or was filtered by basic rules (e.g., bot, too short, irrelevant name). Not adding.") # Log filtered
            return False

        # --- TEMPORARILY DISABLED FOR DEBUGGING ---
        # if self._should_ignore_telegram_channel(standardized_channel):
        #     print(f"SourceManager: TEMPORARILY SKIPPING advanced filtering for Telegram channel '{standardized_channel}'.")
        #     return False
        # --- END DISABLED BLOCK ---

        if standardized_channel in self.telegram_channels:
            # print(f"SourceManager: Channel '{standardized_channel}' already in active list. Not adding.") # Too verbose unless needed
            return False
        
        if standardized_channel in self.timeout_telegram_channels:
            print(f"SourceManager: Channel '{standardized_channel}' is currently timed out. Not adding to active list.") # Log if timed out
            return False

        if self._is_blacklisted_telegram_channel(standardized_channel):
            print(f"SourceManager: Channel '{standardized_channel}' is blacklisted. Not adding.") # Log blacklisted
            return False

        if settings.WHITELIST_TELEGRAM_CHANNELS and standardized_channel not in settings.WHITELIST_TELEGRAM_CHANNELS:
            print(f"SourceManager: Skipping discovered channel {standardized_channel} as it's not in whitelist and whitelist is active. Not adding.") # Log not in whitelist
            return False

        if len(self.telegram_channels) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.telegram_channels.add(standardized_channel)
            self._all_telegram_scores[standardized_channel] = 0 # Initialize score for new channel
            print(f"SourceManager: ADDED new Telegram channel '{standardized_channel}' to active list.") # Success log
            return True
        else:
            print(f"SourceManager: Max discovered Telegram channels limit ({settings.MAX_DISCOVERED_SOURCES_TO_ADD}) reached. Skipping '{standardized_channel}'.") # Limit reached
        return False

    def add_website(self, url: str) -> bool:
        """
        Adds a new website URL to the list of active websites.
        Advanced filtering is TEMPORARILY DISABLED for debugging.
        """
        # --- TEMPORARILY DISABLED FOR DEBUGGING ---
        # if self._should_ignore_website_url(url):
        #     print(f"SourceManager: TEMPORARILY SKIPPING advanced filtering for website URL '{url}'.")
        #     return False
        # --- END DISABLED BLOCK ---

        if url in self.websites:
            # print(f"SourceManager: Website '{url}' already in active list. Not adding.") # Too verbose unless needed
            return False
        
        if url in self.timeout_websites:
            print(f"SourceManager: Website '{url}' is currently timed out. Not adding to active list.") # Log if timed out
            return False

        if self._is_blacklisted_website(url):
            print(f"SourceManager: Website '{url}' is blacklisted. Not adding.") # Log blacklisted
            return False

        if settings.WHITELIST_WEBSITES and url not in settings.WHITELIST_WEBSITES:
            print(f"SourceManager: Skipping discovered website {url} as it's not in whitelist and whitelist is active. Not adding.") # Log not in whitelist
            return False

        if len(self.websites) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.websites.add(url)
            self._all_website_scores[url] = 0 # Initialize score for new website
            print(f"SourceManager: ADDED new website URL '{url}' to active list.") # Success log
            return True
        else:
            print(f"SourceManager: Max discovered websites limit ({settings.MAX_DISCOVERED_SOURCES_TO_ADD}) reached. Skipping '{url}'.") # Limit reached
        return False

    def update_telegram_channel_score(self, channel_username: str, score_change: int):
        """Updates the score of a Telegram channel and potentially moves it to timeout."""
        if channel_username in self._all_telegram_scores:
            old_score = self._all_telegram_scores[channel_username]
            self._all_telegram_scores[channel_username] += score_change
            print(f"SourceManager: Score for '{channel_username}' updated from {old_score} to {self._all_telegram_scores[channel_username]}. Change: {score_change}.") # Detailed score update
            
            if self._all_telegram_scores[channel_username] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
               channel_username not in self.timeout_telegram_channels:
                self._move_telegram_to_timeout(channel_username, self._all_telegram_scores[channel_username])
            elif self._all_telegram_scores[channel_username] > settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
                 channel_username in self.timeout_telegram_channels: # If it's recovered manually or score improved significantly
                print(f"SourceManager: Channel '{channel_username}' has improved score ({self._all_telegram_scores[channel_username]}) and is no longer at timeout threshold. Removing from timeout list if present.")
                self.telegram_channels.add(channel_username) # Add back to active list if it was removed
                self.timeout_telegram_channels.pop(channel_username, None) # Safely remove from timeout dict

        else:
            print(f"SourceManager: WARNING: Attempted to update score for unknown Telegram channel '{channel_username}'. Initializing with score {score_change}.") # Log unknown channel
            self._all_telegram_scores[channel_username] = score_change
            if self._all_telegram_scores[channel_username] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM:
                 self._move_telegram_to_timeout(channel_username, self._all_telegram_scores[channel_username])


    def update_website_score