import httpx # For async HTTP requests
from bs4 import BeautifulSoup # For parsing HTML
import re
import os
import json
from datetime import datetime, timedelta, timezone
import asyncio 
import traceback
from typing import Optional, List, Dict, Tuple 

# Import necessary modules from utils
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
# NEW: Import ConfigParser (no direct regex patterns or ConfigValidator needed here anymore)
from src.parsers.config_parser import ConfigParser 


class TelegramCollector:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=settings.COLLECTION_TIMEOUT_SECONDS)
        # NEW: Initialize ConfigParser to handle all parsing, cleaning, and validation
        self.config_parser = ConfigParser() 
        print("TelegramCollector: Initialized for Telegram Web (t.me/s/) collection.")

    async def _fetch_channel_page(self, channel_username: str) -> Optional[str]:
        """Fetches the HTML content of a Telegram Web channel page."""
        clean_username = channel_username.lstrip('@')
        url = f"https://t.me/s/{clean_username}" # Public Telegram Web URL
        print(f"TelegramCollector: Attempting to fetch channel page: {url}") # Detailed log

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9,fa;q=0.8"
            }
            response = await self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            print(f"TelegramCollector: Successfully fetched {url}. Status: {response.status_code}") # Success log
            return response.text
        except httpx.TimeoutException:
            print(f"TelegramCollector: ERROR: Timeout fetching {url}") # Detailed error
            source_manager.update_telegram_channel_score(channel_username, -settings.COLLECTION_TIMEOUT_SECONDS)
            return None
        except httpx.HTTPStatusError as e:
            print(f"TelegramCollector: ERROR: HTTP Error {e.response.status_code} fetching {url}. Response text snippet: {e.response.text.strip()[:200]}...") # Detailed error
            if e.response.status_code == 404:
                source_manager.update_telegram_channel_score(channel_username, -100)
                print(f"TelegramCollector: Channel {channel_username} not found (404). Consider blacklisting.")
            elif e.response.status_code == 429:
                print(f"TelegramCollector: Rate limit hit for {url} (429). Consider increasing delay or using proxies.")
                source_manager.update_telegram_channel_score(channel_username, -50)
            else:
                source_manager.update_telegram_channel_score(channel_username, -20)
            return None
        except httpx.RequestError as e:
            print(f"TelegramCollector: ERROR: Request error fetching {url}: {e}") # Detailed error
            source_manager.update_telegram_channel_score(channel_username, -15)
            return None
        except Exception as e:
            print(f"TelegramCollector: ERROR: An unexpected error occurred fetching {url}: {e}") # Detailed error
            traceback.print_exc() # Print full traceback for unexpected errors
            source_manager.update_telegram_channel_score(channel_username, -25)
            return None

    def _extract_date_from_message_html(self, message_soup_tag: BeautifulSoup) -> Optional[datetime]:
        """Extracts datetime from a BeautifulSoup message tag."""
        try:
            time_element = message_soup_tag.find('time', class_='time')
            if time_element and 'datetime' in time_element.attrs:
                return datetime.fromisoformat(time_element['datetime'])
        except Exception:
            # print("TelegramCollector: Could not extract date from message HTML.") # Too verbose, skip this.
            pass
        return None

    def _is_config_recent(self, message_date: Optional[datetime]) -> bool:
        """Checks if a config message is within the lookback duration."""
        if not message_date:
            # print("TelegramCollector: Message date is None, considering recent.") # Too verbose
            return True

        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)

        cutoff_date = datetime.now(timezone.utc) - settings.TELEGRAM_MESSAGE_LOOKBACK_DURATION
        is_recent = message_date >= cutoff_date
        # if not is_recent: print(f"TelegramCollector: Message date {message_date} is too old (cutoff: {cutoff_date}).") # Too verbose
        return is_recent

    async def _discover_and_add_channel(self, raw_channel_input: str):
        """
        Discovers a new Telegram channel and adds it to the SourceManager if enabled.
        """
        if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY:
            standardized_channel_name = source_manager._standardize_channel_username(raw_channel_input)
            if standardized_channel_name:
                print(f"TelegramCollector: Attempting to discover/add channel: {standardized_channel_name} from raw input: {raw_channel_input}") # Detailed log
                if source_manager.add_telegram_channel(standardized_channel_name):
                    stats_reporter.increment_discovered_channel_count()
                    print(f"TelegramCollector: Discovered and ADDED new channel: {standardized_channel_name}")
                else:
                    print(f"TelegramCollector: Channel {standardized_channel_name} already exists, blacklisted, or max discovery limit reached. Not added.") # Detailed log
            else:
                print(f"TelegramCollector: Raw channel input '{raw_channel_input}' could not be standardized or was ignored by SourceManager filtering.") # Detailed log

    async def collect_from_channel(self, channel_username: str) -> List[Dict]:
        """
        Collects config links from a single Telegram channel page (t.me/s/).
        Parses HTML, extracts text from various message components, and discovers new channels.
        """
        collected_links: List[Dict] = []
        html_content = await self._fetch_channel_page(channel_username)

        if not html_content:
            print(f"TelegramCollector: No HTML content for {channel_username}. Skipping parsing.") # Detailed log
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        messages_html = soup.find_all('div', class_='tgme_widget_message_wrap')

        if not messages_html:
            print(f"TelegramCollector: No messages found on channel page {channel_username} using BeautifulSoup. Score -1.") # Detailed log
            source_manager.update_telegram_channel_score(channel_username, -1)
            return []
        else:
            print(f"TelegramCollector: Found {len(messages_html)} message HTML wrappers for {channel_username}.") # Detailed log

        messages_with_dates: List[Tuple[Optional[datetime], BeautifulSoup, BeautifulSoup]] = []
        for msg_wrap in messages_html:
            message_text_div = msg_wrap.find('div', class_='tgme_widget_message_text')
            if not message_text_div:
                # print("TelegramCollector: Message wrapper without tgme_widget_message_text div. Skipping.") # Too verbose
                continue

            msg_date = self._extract_date_from_message_html(msg_wrap)
            messages_with_dates.append((msg_date, message_text_div, msg_wrap))

        messages_with_dates.sort(key=lambda x: x[0] if x[0] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        processed_message_count: int = 0
        for msg_date, message_text_div, msg_wrap in messages_with_dates:
            if not self._is_config_recent(msg_date):
                print(f"TelegramCollector: Message from {msg_date} is too old for {channel_username}. Skipping further messages in this channel.") # Detailed log
                break # Assuming messages are sorted by date, no need to check older ones.

            if settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL is not None and processed_message_count >= settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL:
                print(f"TelegramCollector: Max messages per channel limit ({settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL}) reached for {channel_username}. Stopping message processing.") # Detailed log
                break

            processed_message_count += 1
            # print(f"TelegramCollector: Processing message {processed_message_count} from {msg_date} in {channel_username}.") # Too verbose unless needed

            # Combine all relevant text from different parts of the message
            all_message_text = message_text_div.get_text(separator='\n', strip=True) # Use \n for better splitting

            # NEW: Delegate parsing, cleaning, and validation to ConfigParser
            # ConfigParser will return fully validated and cleaned links.
            parsed_links_info = self.config_parser.parse_content(all_message_text)

            if not parsed_links_info:
                # print(f"TelegramCollector: No config links parsed from message {processed_message_count} in {channel_username}.") # Too verbose
                pass # This is normal if a message doesn't contain configs

            for link_info in parsed_links_info:
                protocol = link_info.get('protocol')
                link = link_info.get('link')
                
                if protocol and link: # Ensure protocol and link are valid from parser
                    # Filter based on active protocols in settings
                    if protocol in settings.ACTIVE_PROTOCOLS:
                        collected_links.append({'protocol': protocol, 'link': link})
                        stats_reporter.increment_total_collected()
                        stats_reporter.increment_protocol_count(protocol)
                        stats_reporter.record_source_link("telegram", channel_username, protocol)
                        print(f"TelegramCollector: Found valid link ({protocol}) in {channel_username}: {link[:100]}...") # Found link log
                    # Handle 'subscription' protocol specifically if parse_content returns it (e.g., from Clash/Singbox)
                    elif protocol == 'subscription':
                        print(f"TelegramCollector: Found subscription URL: {link}. Attempting to add as a new source from {channel_username}.") # Subscription link discovery log
                        await self._discover_and_add_channel(link) # Treat as a new channel for discovery
                    else:
                        print(f"TelegramCollector: Found link with inactive or unknown protocol '{protocol}' in {channel_username}: {link[:100]}...") # Inactive protocol log
                else:
                    print(f"TelegramCollector: Parser returned invalid link_info: {link_info} from {channel_username}.") # Invalid link_info from parser

            # --- Discovering new channels from message HTML ---
            if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY:
                for a_tag in message_text_div.find_all('a', href=True):
                    href = a_tag['href']
                    if 't.me/' in href:
                        await self._discover_and_add_channel(href)
                    elif href.startswith('@'):
                         await self._discover_and_add_channel(href)

        collected_links = list({item['link']: item for item in collected_links}.values()) # Ensure uniqueness

        if not collected_links:
            print(f"TelegramCollector: No unique config links found in {channel_username} after all processing. Score -1.") # Detailed log
            source_manager.update_telegram_channel_score(channel_username, -1)
        else:
            print(f"TelegramCollector: Successfully found {len(collected_links)} unique valid links in {channel_username}. Score +1.") # Detailed log
            source_manager.update_telegram_channel_score(channel_username, 1)

        return collected_links

    async def collect_from_telegram(self) -> List[Dict]:
        """Main method to collect from all active Telegram channels."""
        all_collected_links: List[Dict] = []
        active_channels: List[str] = source_manager.get_active_telegram_channels()

        if not active_channels:
            print("TelegramCollector: No active Telegram channels to process. This could be due to all channels being timed out or filtered.") # Detailed log
            return []
        else:
            print(f"TelegramCollector: Starting collection from {len(active_channels)} active Telegram channels.") # Detailed log

        tasks = []
        for channel in active_channels:
            tasks.append(self.collect_from_channel(channel))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            channel = active_channels[i]
            if isinstance(result, Exception):
                print(f"TelegramCollector: FATAL ERROR processing channel {channel}: {result}") # Critical error log
                traceback.print_exc()
                source_manager.update_telegram_channel_score(channel, -15)
            elif result:
                all_collected_links.extend(result)

        for channel_name in list(source_manager.timeout_telegram_channels.keys()):
            # Check if this channel was processed and is now timed out in source_manager's internal score
            # and was one of the initially active channels.
            # Compare to settings.MAX_TIMEOUT_SCORE_TELEGRAM
            if channel_name in source_manager._all_telegram_scores and \
               source_manager._all_telegram_scores[channel_name] <= settings.MAX_TIMEOUT_SCORE_TELEGRAM and \
               channel_name in active_channels: # Only add to newly timed out if it was an active channel
                stats_reporter.add_newly_timed_out_channel(channel_name)

        print(f"TelegramCollector: Finished collection. Total links from Telegram: {len(all_collected_links)}")
        return all_collected_links

    async def close(self):
        """Closes the HTTP client session."""
        await self.client.aclose()
        print("TelegramCollector: HTTP client closed.")