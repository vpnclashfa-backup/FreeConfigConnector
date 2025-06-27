# src/utils/source_manager.py

import os
import json
from src.utils.settings_manager import settings
from datetime import datetime, timedelta, timezone

class SourceManager:
    def __init__(self):
        self.telegram_channels = self._load_sources_from_file(settings.CHANNELS_FILE)
        self.websites = self._load_sources_from_file(settings.WEBSITES_FILE)

        # Load timeout sources. These will be dictionaries with {source: {"score": X, "last_timeout": datetime_str}}
        self.timeout_telegram_channels = self._load_timeout_sources(settings.TIMEOUT_TELEGRAM_CHANNELS_FILE)
        self.timeout_websites = self._load_timeout_sources(settings.TIMEOUT_WEBSITES_FILE)

        # Initialize internal scores for active sources, merging with timeout scores
        self._active_telegram_scores = {s: self.timeout_telegram_channels.get(s, {}).get("score", 0) for s in self.telegram_channels}
        self._active_website_scores = {s: self.timeout_websites.get(s, {}).get("score", 0) for s in self.websites}

        print(f"Loaded {len(self.telegram_channels)} Telegram channels and {len(self.websites)} websites.")
        print(f"Loaded {len(self.timeout_telegram_channels)} timeout Telegram channels and {len(self.timeout_websites)} timeout websites.")

    def _load_sources_from_file(self, file_path):
        """Loads sources (channels/websites) from a plain text file."""
        if not os.path.exists(file_path):
            print(f"Warning: Source file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                pass
            return set()
        with open(file_path, 'r', encoding='utf-8') as f:
            # هر خط را بخوان و فضاهای اضافی را حذف کن، سپس به set تبدیل کن برای حذف تکراری‌ها
            return {line.strip() for line in f if line.strip()}

    def _save_sources_to_file(self, sources_set, file_path):
        """Saves sources (channels/websites) to a plain text file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            for source in sorted(list(sources_set)): # مرتب‌سازی برای خوانایی بهتر
                f.write(source + '\n')

    def _load_timeout_sources(self, file_path):
        """Loads timeout sources from a JSON file, including scores and last timeout time."""
        if not os.path.exists(file_path):
            print(f"Warning: Timeout file not found at {file_path}. Creating an empty one.")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f) # Save empty JSON object
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects if needed, or keep as string
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

    def add_telegram_channel(self, channel_username):
        """Adds a new Telegram channel to the list of active channels."""
        if channel_username.lower().endswith("bot"): # دوباره چک می کنیم که ربات نباشد
            return False

        standardized_channel = self._standardize_channel_username(channel_username)
        if not standardized_channel: # اگر استانداردسازی منجر به None شد (مثلا ربات بود)
            return False

        if standardized_channel not in self.telegram_channels and \
           standardized_channel not in self.timeout_telegram_channels and \
           not self._is_blacklisted_telegram_channel(standardized_channel):

            # بررسی Whitelist
            if settings.WHITELIST_TELEGRAM_CHANNELS and standardized_channel not in settings.WHITELIST_TELEGRAM_CHANNELS:
                print(f"Skipping discovered channel {standardized_channel} as it's not in whitelist.")
                return False

            if len(self.telegram_channels) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
                self.telegram_channels.add(standardized_channel)
                self._active_telegram_scores[standardized_channel] = 0 # امتیازدهی اولیه
                print(f"Added new Telegram channel to active list: {standardized_channel}")
                return True
            else:
                print(f"Max discovered Telegram channels limit reached. Skipping {standardized_channel}")
        return False

    def add_website(self, url):
        """Adds a new website URL to the list of active websites."""
        if url not in self.websites and \
           url not in self.timeout_websites and \
           not self._is_blacklisted_website(url):

            # بررسی Whitelist
            if settings.WHITELIST_WEBSITES and url not in settings.WHITELIST_WEBSITES:
                print(f"Skipping discovered website {url} as it's not in whitelist.")
                return False

            if len(self.websites) < (settings.MAX_DISCOVERED_SOURCES_TO_ADD if settings.MAX_DISCOVERED_SOURCES_TO_ADD > 0 else float('inf')):
                self.websites.add(url)
                self._active_website_scores[url] = 0 # امتیازدهی اولیه
                print(f"Added new website to active list: {url}")
                return True
            else:
                print(f"Max discovered websites limit reached. Skipping {url}")
        return False

    def update_telegram_channel_score(self, channel_username, score_change):
        """Updates the score of a Telegram channel."""
        if channel_username in self._active_telegram_scores:
            self._active_telegram_scores[channel_username] += score_change
            print(f"Score for {channel_username} updated to {self._active_telegram_scores[channel_username]}")
            # اگر امتیاز به حدی رسید که باید تایم‌اوت شود
            if self._active_telegram_scores[channel_username] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM:
                self._move_telegram_to_timeout(channel_username, self._active_telegram_scores[channel_username])

    def update_website_score(self, url, score_change):
        """Updates the score of a website."""
        if url in self._active_website_scores:
            self._active_website_scores[url] += score_change
            print(f"Score for {url} updated to {self._active_website_scores[url]}")
            # اگر امتیاز به حدی رسید که باید تایم‌اوت شود
            if self._active_website_scores[url] <= settings.MAX_TIMEOUT_SCORE_WEB:
                self._move_website_to_timeout(url, self._active_website_scores[url])

    def _move_telegram_to_timeout(self, channel_username, score):
        """Moves a Telegram channel from active to timeout list."""
        print(f"Channel {channel_username} reached timeout score. Moving to timeout list.")
        self.telegram_channels.discard(channel_username) # حذف از لیست فعال
        self.timeout_telegram_channels[channel_username] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}
        del self._active_telegram_scores[channel_username] # حذف از دیکشنری امتیازدهی فعال

    def _move_website_to_timeout(self, url, score):
        """Moves a website from active to timeout list."""
        print(f"Website {url} reached timeout score. Moving to timeout list.")
        self.websites.discard(url) # حذف از لیست فعال
        self.timeout_websites[url] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}
        del self._active_website_scores[url] # حذف از دیکشنری امتیازدهی فعال

    def get_active_telegram_channels(self):
        """Returns the list of Telegram channels that are active and not timed out."""
        # فقط کانال‌هایی که در لیست سیاه نیستند و در لیست تایم‌اوت نیستند
        active_channels = []
        for channel in self.telegram_channels:
            if not self._is_blacklisted_telegram_channel(channel) and \
               not self._is_timed_out_telegram_channel(channel) and \
               self._is_whitelisted_telegram_channel(channel): # بررسی whitelist
                active_channels.append(channel)
        return list(active_channels)

    def get_active_websites(self):
        """Returns the list of websites that are active and not timed out."""
        # فقط وب‌سایت‌هایی که در لیست سیاه نیستند و در لیست تایم‌اوت نیستند
        active_websites = []
        for website in self.websites:
            if not self._is_blacklisted_website(website) and \
               not self._is_timed_out_website(website) and \
               self._is_whitelisted_website(website): # بررسی whitelist
                active_websites.append(website)
        return list(active_websites)

    def _is_blacklisted_telegram_channel(self, channel_username):
        return channel_username in settings.BLACKLIST_TELEGRAM_CHANNELS

    def _is_blacklisted_website(self, url):
        return url in settings.BLACKLIST_WEBSITES

    def _is_whitelisted_telegram_channel(self, channel_username):
        # اگر لیست سفید خالی باشد، همه چیز مجاز است. در غیر این صورت، باید در لیست سفید باشد.
        return not settings.WHITELIST_TELEGRAM_CHANNELS or channel_username in settings.WHITELIST_TELEGRAM_CHANNELS

    def _is_whitelisted_website(self, url):
        return not settings.WHITELIST_WEBSITES or url in settings.WHITELIST_WEBSITES

    def _is_timed_out_telegram_channel(self, channel_username):
        """Checks if a Telegram channel is currently in a timeout state."""
        if channel_username in self.timeout_telegram_channels:
            # می‌توانید اینجا یک منطق برای بازگرداندن از تایم‌اوت بعد از یک مدت زمان مشخص اضافه کنید
            # فعلاً فقط بررسی می‌کنیم که در دیکشنری تایم‌اوت هست یا نه
            return True
        return False

    def _is_timed_out_website(self, url):
        """Checks if a website is currently in a timeout state."""
        if url in self.timeout_websites:
            return True
        return False

    def finalize(self):
        """Saves all current source lists and timeout lists to files."""
        print("Saving source manager state...")
        self._save_sources_to_file(self.telegram_channels, settings.CHANNELS_FILE)
        self._save_sources_to_file(self.websites, settings.WEBSITES_FILE)

        # قبل از ذخیره، امتیازهای فعال را به لیست تایم‌اوت منتقل می‌کنیم
        # این کار مطمئن می‌شود که امتیاز کانال‌هایی که در حال حاضر فعال هستند نیز حفظ می‌شود
        for channel, score in self._active_telegram_scores.items():
            self.timeout_telegram_channels[channel] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}
        for website, score in self._active_website_scores.items():
            self.timeout_websites[website] = {"score": score, "last_timeout": datetime.now(timezone.utc).isoformat()}

        self._save_timeout_sources(self.timeout_telegram_channels, settings.TIMEOUT_TELEGRAM_CHANNELS_FILE)
        self._save_timeout_sources(self.timeout_websites, settings.TIMEOUT_WEBSITES_FILE)
        print("Source manager state saved.")

    # Helper to standardize channel username (similar to telegram_collector's version)
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
