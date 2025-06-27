# src/utils/source_manager.py

import os
import json
from src.utils.settings_manager import settings
from datetime import datetime, timedelta, timezone

class SourceManager:
    def __init__(self):
        self.telegram_channels = self._load_sources_from_file(settings.CHANNELS_FILE)
        self.websites = self._load_sources_from_file(settings.WEBSITES_FILE)

        self.timeout_telegram_channels = self._load_timeout_sources(settings.TIMEOUT_TELEGRAM_CHANNELS_FILE)
        self.timeout_websites = self._load_timeout_sources(settings.TIMEOUT_WEBSITES_FILE)

        # Initialize internal scores for all known sources, merging with timeout scores
        # This ensures we retain scores even if a source is currently timed out
        self._all_telegram_scores = {}
        for s in self.telegram_channels:
            self._all_telegram_scores[s] = self.timeout_telegram_channels.get(s, {}).get("score", 0)
        # Add back channels that were timed out but are now potentially recoverable
        for s, data in self.timeout_telegram_channels.items():
            if s not in self._all_telegram_scores:
                self._all_telegram_scores[s] = data.get("score", 0)

        self._all_website_scores = {}
        for s in self.websites:
            self._all_website_scores[s] = self.timeout_websites.get(s, {}).get("score", 0)
        for s, data in self.timeout_websites.items():
            if s not in self._all_website_scores:
                self._all_website_scores[s] = data.get("score", 0)

        print(f"Loaded {len(self.telegram_channels)} initial Telegram channels and {len(self.websites)} initial websites.")
        print(f"Loaded {len(self.timeout_telegram_channels)} previously timed out Telegram channels and {len(self.timeout_websites)} previously timed out websites.")

        self._recover_timed_out_sources() # Try to recover sources at startup

    def _load_sources_from_file(self, file_path):
        """Loads sources (channels/websites) from a plain text file."""
        if not os.path.exists(file_path):
            print(f"Warning: Source file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                pass
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            return {line.strip() for line in f if line.strip()}

    def _save_sources_to_file(self, sources_set, file_path):
        """Saves sources (channels/websites) to a plain text file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            for source in sorted(list(sources_set)):
                f.write(source + '\n')

    def _load_timeout_sources(self, file_path):
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
                # Optionally convert 'last_timeout' string to datetime object here if needed for direct comparison
                return data
        except json.JSONDecodeError as e:
            print(f"Error reading timeout file {file_path}: Invalid JSON format. {e}")
            return {}
        except Exception as e:
            print(f"An unexpected error occurred while loading timeout file {file_path}: {e}")
            return {}

    def _save_timeout_sources(self, timeout_dict, file_path):
        """Saves timeout sources to a JSON file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(timeout_dict, f, indent=4, ensure_ascii=False)

    def _recover_timed_out_sources(self):
        """Attempts to recover sources from timeout lists if enough time has passed."""
        now = datetime.now(timezone.utc)

        # Recover Telegram channels
        channels_to_recover = []
        for channel, data in list(self.timeout_telegram_channels.items()): # Use list() to allow modification during iteration
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                channels_to_recover.append(channel)
                print(f"Recovering Telegram channel from timeout: {channel}")
        for channel in channels_to_recover:
            self.telegram_channels.add(channel) # Add back to active set
            del self.timeout_telegram_channels[channel] # Remove from timeout dict

        # Recover websites
        websites_to_recover = []
        for website, data in list(self.timeout_websites.items()):
            last_timeout_dt = datetime.fromisoformat(data["last_timeout"])
            if now - last_timeout_dt > settings.TIMEOUT_RECOVERY_DURATION:
                websites_to_recover.append(website)
                print(f"Recovering website from timeout: {website}")
        for website in websites_to_recover:
            self.websites.add(website) # Add back to active set
            del self.timeout_websites[website] # Remove from timeout dict

    def add_telegram_channel(self, channel_username):
        """Adds a new Telegram channel to the list of active channels."""
        standardized_channel = self._standardize_channel_username(channel_username)
        if not standardized_channel:
            return False

        # Don't add if already active, in timeout, or blacklisted
        if standardized_channel in self.telegram_channels or \
           standardized_channel in self.timeout_telegram_channels or \
           self._is_blacklisted_telegram_channel(standardized_channel):
            return False

        # Check Whitelist
        if settings.WHITELIST_TELEGRAM_CHANNELS and standardized_channel not in settings.WHITELIST_TELEGRAM_CHANNELS:
            print(f"Skipping discovered channel {standardized_channel} as it's not in whitelist.")
            return False

        if len(self.telegram_channels) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.telegram_channels.add(standardized_channel)
            self._all_telegram_scores[standardized_channel] = 0 # Initialize score for new channel
            print(f"Added new Telegram channel to active list: {standardized_channel}")
            return True
        else:
            print(f"Max discovered Telegram channels limit reached. Skipping {standardized_channel}")
        return False

    def add_website(self, url):
        """Adds a new website URL to the list of active websites."""
        if url in self.websites or \
           url in self.timeout_websites or \
           self._is_blacklisted_website(url):
            return False

        if settings.WHITELIST_WEBSITES and url not in settings.WHITELIST_WEBSITES:
            print(f"Skipping discovered website {url} as it's not in whitelist.")
            return False

        if len(self.websites) < (settings.MAX_DISCOVERED_SOURCES_TO_add if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
            self.websites.add(url)
            self._all_website_scores[url] = 0 # Initialize score for new website
            print(f"Added new website to active list: {url}")
            return True
        else:
            print(f"Max discovered websites limit reached. Skipping {url}")
        return False

    def update_telegram_channel_score(self, channel_username, score_change):
        """Updates the score of a Telegram channel and potentially moves it to timeout."""
        if channel_username in self._all_telegram_scores: # Ensure it's a known channel
            self._all_telegram_scores[channel_username] += score_change
            print(f"Score for {channel_username} updated to {self._all_telegram_scores[channel_username]}")

            if self._all_telegram_scores[channel_username] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
               channel_username not in self.timeout_telegram_channels: # Prevent re-timing out if already there
                self._move_telegram_to_timeout(channel_username, self._all_telegram_scores[channel_username])

    def update_website_score(self, url, score_change):
        """Updates the score of a website and potentially moves it to timeout."""
        if url in self._all_website_scores: # Ensure it's a known website
            self._all_website_scores[url] += score_change
            print(f"Score for {url} updated to {self._all_website_scores[url]}")

            if self._all_website_scores[url] <= settings.MAX_TIMEOUT_SCORE_WEB and \
               url not in self.timeout_websites:
                self._move_website_to_timeout(url, self._all_website_scores[url])

    def _move_telegram_to_timeout(self, channel_username, score):
        """Moves a Telegram channel from active to timeout list."""
        print(f"Channel {channel_username} reached timeout score ({score}). Moving to timeout list.")
        self.telegram_channels.discard(channel_username) # Remove from active set
        self.timeout_telegram_channels[channel_username] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}
        # Note: We keep score in _all_telegram_scores for consistency, just remove from active set

    def _move_website_to_timeout(self, url, score):
        """Moves a website from active to timeout list."""
        print(f"Website {url} reached timeout score ({score}). Moving to timeout list.")
        self.websites.discard(url) # Remove from active set
        self.timeout_websites[url] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}

    def get_active_telegram_channels(self):
        """Returns Telegram channels that are active, not blacklisted, not currently timed out, and optionally whitelisted, sorted by score (highest first)."""

        # Filter channels that are currently active and meet whitelist/blacklist criteria
        eligible_channels = []
        for channel in self.telegram_channels: # Iterate through the set of channels marked as "active"
            if not self._is_blacklisted_telegram_channel(channel) and \
               not self._is_timed_out_telegram_channel(channel) and \
               self._is_whitelisted_telegram_channel(channel):
                eligible_channels.append(channel)

        # Sort eligible channels by their score
        # We use _all_telegram_scores which holds scores for all known channels, active or not.
        sorted_channels = sorted(eligible_channels, key=lambda ch: self._all_telegram_scores.get(ch, 0), reverse=True)
        return sorted_channels

    def get_active_websites(self):
        """Returns websites that are active, not blacklisted, not currently timed out, and optionally whitelisted, sorted by score (highest first)."""
        eligible_websites = []
        for website in self.websites:
            if not self._is_blacklisted_website(website) and \
               not self._is_timed_out_website(website) and \
               self._is_whitelisted_website(website):
                eligible_websites.append(website)

        sorted_websites = sorted(eligible_websites, key=lambda w: self._all_website_scores.get(w, 0), reverse=True)
        return sorted_websites

    def get_timed_out_telegram_channels(self):
        """Returns a list of Telegram channels currently in timeout state, sorted by score (lowest first)."""
        # Convert to list of (channel, score) tuples, then sort
        timeout_list = []
        for channel, data in self.timeout_telegram_channels.items():
            timeout_list.append((channel, data.get("score", 0)))

        # Sort by score ascending (lowest score first)
        return [ch for ch, score in sorted(timeout_list, key=lambda item: item[1])]

    def get_timed_out_websites(self):
        """Returns a list of websites currently in timeout state, sorted by score (lowest first)."""
        timeout_list = []
        for website, data in self.timeout_websites.items():
            timeout_list.append((website, data.get("score", 0)))

        return [w for w, score in sorted(timeout_list, key=lambda item: item[1])]


    def _is_blacklisted_telegram_channel(self, channel_username):
        return channel_username in settings.BLACKLIST_TELEGRAM_CHANNELS

    def _is_blacklisted_website(self, url):
        return url in settings.BLACKLIST_WEBSITES

    def _is_whitelisted_telegram_channel(self, channel_username):
        return not settings.WHITELIST_TELEGRAM_CHANNELS or channel_username in settings.WHITELIST_TELEGRAM_CHANNELS

    def _is_whitelisted_website(self, url):
        return not settings.WHITELIST_WEBSITES or url in settings.WHITELIST_WEBSITES

    def _is_timed_out_telegram_channel(self, channel_username):
        """Checks if a Telegram channel is in timeout and if it should recover."""
        if channel_username in self.timeout_telegram_channels:
            last_timeout_str = self.timeout_telegram_channels[channel_username].get("last_timeout")
            if last_timeout_str:
                last_timeout_dt = datetime.fromisoformat(last_timeout_str)
                # اگر از مدت بازیابی گذشته باشد، آن را از تایم‌اوت حذف نمی‌کنیم تا در finalize ذخیره شود
                # اما آن را از نظر عملیاتی "تایم‌اوت" در نظر نمی‌گیریم
                return datetime.now(timezone.utc) - last_timeout_dt < settings.TIMEOUT_RECOVERY_DURATION
        return False

    def _is_timed_out_website(self, url):
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
        # Save active sources (telegram_channels, websites) back to their text files
        self._save_sources_to_file(self.telegram_channels, settings.CHANNELS_FILE)
        self._save_sources_to_file(self.websites, settings.WEBSITES_FILE)

        # Update scores in timeout dict for currently active sources
        # This ensures even if a source didn't time out, its score is saved for next run
        for channel, score in self._all_telegram_scores.items():
            self.timeout_telegram_channels[channel] = {"score": score, "last_timeout": self.timeout_telegram_channels.get(channel, {}).get("last_timeout", datetime.now(timezone.utc).isoformat())}
        for website, score in self._all_website_scores.items():
            self.timeout_websites[website] = {"score": score, "last_timeout": self.timeout_websites.get(website, {}).get("last_timeout", datetime.now(timezone.utc).isoformat())}

        self._save_timeout_sources(self.timeout_telegram_channels, settings.TIMEOUT_TELEGRAM_CHANNELS_FILE)
        self._save_timeout_sources(self.timeout_websites, settings.TIMEOUT_WEBSITES_FILE)
        print("Source manager state saved.")

    def _standardize_channel_username(self, raw_input):
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
