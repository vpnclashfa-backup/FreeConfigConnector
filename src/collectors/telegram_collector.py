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
        print(f"TelegramCollector: Fetching channel page: {url}")

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9,fa;q=0.8"
            }
            response = await self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except httpx.TimeoutException:
            print(f"TelegramCollector: Timeout fetching {url}")
            source_manager.update_telegram_channel_score(channel_username, -settings.COLLECTION_TIMEOUT_SECONDS)
            return None
        except httpx.HTTPStatusError as e:
            print(f"TelegramCollector: HTTP Error {e.response.status_code} fetching {url}: {e.response.text.strip()[:100]}...")
            if e.response.status_code == 404:
                source_manager.update_telegram_channel_score(channel_username, -100)
                print(f"TelegramCollector: Channel {channel_username} not found. Consider blacklisting.")
            elif e.response.status_code == 429:
                print(f"TelegramCollector: Rate limit hit for {url}. Consider increasing delay or using proxies.")
                source_manager.update_telegram_channel_score(channel_username, -50)
            else:
                source_manager.update_telegram_channel_score(channel_username, -20)
            return None
        except httpx.RequestError as e:
            print(f"TelegramCollector: Request error fetching {url}: {e}")
            source_manager.update_telegram_channel_score(channel_username, -15)
            return None
        except Exception as e:
            print(f"TelegramCollector: An unexpected error occurred fetching {url}: {e}")
            source_manager.update_telegram_channel_score(channel_username, -25)
            return None

    def _extract_date_from_message_html(self, message_soup_tag: BeautifulSoup) -> Optional[datetime]:
        """Extracts datetime from a BeautifulSoup message tag."""
        try:
            time_element = message_soup_tag.find('time', class_='time')
            if time_element and 'datetime' in time_element.attrs:
                return datetime.fromisoformat(time_element['datetime'])
        except Exception:
            pass
        return None

    def _is_config_recent(self, message_date: Optional[datetime]) -> bool:
        """Checks if a config message is within the lookback duration."""
        if not message_date:
            return True

        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)

        cutoff_date = datetime.now(timezone.utc) - settings.TELEGRAM_MESSAGE_LOOKBACK_DURATION
        return message_date >= cutoff_date

    async def _discover_and_add_channel(self, raw_channel_input: str):
        """
        Discovers a new Telegram channel and adds it to the SourceManager if enabled.
        """
        if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY:
            standardized_channel_name = source_manager._standardize_channel_username(raw_channel_input)
            if standardized_channel_name:
                if source_manager.add_telegram_channel(standardized_channel_name):
                    stats_reporter.increment_discovered_channel_count()
                    print(f"TelegramCollector: Discovered and added new channel: {standardized_channel_name}")

    async def collect_from_channel(self, channel_username: str) -> List[Dict]:
        """
        Collects config links from a single Telegram channel page (t.me/s/).
        Parses HTML, extracts text from various message components, and discovers new channels.
        """
        collected_links: List[Dict] = []
        html_content = await self._fetch_channel_page(channel_username)

        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        messages_html = soup.find_all('div', class_='tgme_widget_message_wrap')

        if not messages_html:
            print(f"TelegramCollector: No messages found on channel page {channel_username}. Score -1.")
            source_manager.update_telegram_channel_score(channel_username, -1)
            return []

        messages_with_dates: List[Tuple[Optional[datetime], BeautifulSoup, BeautifulSoup]] = []
        for msg_wrap in messages_html:
            message_text_div = msg_wrap.find('div', class_='tgme_widget_message_text')
            if not message_text_div: continue

            msg_date = self._extract_date_from_message_html(msg_wrap)
            messages_with_dates.append((msg_date, message_text_div, msg_wrap))

        messages_with_dates.sort(key=lambda x: x[0] if x[0] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        processed_message_count: int = 0
        for msg_date, message_text_div, msg_wrap in messages_with_dates:
            if not self._is_config_recent(msg_date):
                continue

            if settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL is not None and processed_message_count >= settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL:
                print(f"TelegramCollector: Max messages per channel limit ({settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL}) reached for {channel_username}.")
                break

            processed_message_count += 1

            # Combine all relevant text from different parts of the message
            all_message_text = message_text_div.get_text(separator=' ', strip=True)

            # NEW: Delegate parsing, cleaning, and validation to ConfigParser
            # ConfigParser will return fully validated and cleaned links.
            parsed_links_info = self.config_parser.parse_content(all_message_text)

            for link_info in parsed_links_info:
                protocol = link_info.get('protocol')
                link = link_info.get('link')
                
                if protocol and link: # Ensure protocol and link are valid
                    # Filter based on active protocols in settings
                    if protocol in settings.ACTIVE_PROTOCOLS:
                        collected_links.append({'protocol': protocol, 'link': link})
                        stats_reporter.increment_total_collected()
                        stats_reporter.increment_protocol_count(protocol)
                        stats_reporter.record_source_link("telegram", channel_username, protocol)
                    # Handle 'subscription' protocol specifically if parse_content returns it (e.g., from Clash/Singbox)
                    elif protocol == 'subscription':
                        print(f"TelegramCollector: Found subscription URL: {link}. Attempting to add as a new source.")
                        await self._discover_and_add_channel(link) # Treat as a new channel for discovery


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
            print(f"TelegramCollector: No config links found in {channel_username} within the specified criteria.")
            source_manager.update_telegram_channel_score(channel_username, -1)
        else:
            print(f"TelegramCollector: Found {len(collected_links)} unique links in {channel_username}.")
            source_manager.update_telegram_channel_score(channel_username, 1)

        return collected_links

    async def collect_from_telegram(self) -> List[Dict]:
        """Main method to collect from all active Telegram channels."""
        all_collected_links: List[Dict] = []
        active_channels: List[str] = source_manager.get_active_telegram_channels()

        if not active_channels:
            print("TelegramCollector: No active Telegram channels to process.")
            return []

        tasks = []
        for channel in active_channels:
            tasks.append(self.collect_from_channel(channel))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            channel = active_channels[i]
            if isinstance(result, Exception):
                print(f"TelegramCollector: Error processing channel {channel}: {result}")
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