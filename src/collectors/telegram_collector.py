# src/collectors/telegram_collector.py

import httpx # For async HTTP requests
from bs4 import BeautifulSoup # For parsing HTML
import re
import os
import json
from datetime import datetime, timedelta, timezone
import asyncio 
import traceback
from typing import Optional # NEW: Import Optional type hint
    
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
# get_config_regex_patterns را از parser هم می‌توانستیم بگیریم، اما فعلا در همین فایل نگه می‌داریم تا بعداً منتقل شود
# For now, it remains here but understand it's a shared utility
# We will introduce a common parser module in a future step.

# این تابع الگوهای RegEx را برای پروتکل‌های مختلف VPN/پروکسی تعریف می‌کند.
def get_config_regex_patterns():
    patterns = {}
    base_pattern_suffix = r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+"

    protocol_regex_map = {
        "http": r"https?:\/\/" + base_pattern_suffix,
        "socks5": r"socks5:\/\/" + base_pattern_suffix,
        "ss": r"ss:\/\/[a-zA-Z0-9\+\/=]{20,}(?:@[a-zA-Z0-9\.\-]+:\d{1,5})?(?:#.*)?",
        "ssr": r"ssr:\/\/[a-zA-Z0-9\+\/=]{20,}(?:@[a-zA-Z0-9\.\-]+:\d{1,5})?(?:#.*)?",
        "vmess": r"vmess:\/\/[a-zA-Z0-9\+\/=]+",
        "vless": r"vless:\/\/" + base_pattern_suffix,
        "trojan": r"trojan:\/\/" + base_pattern_suffix,
        "reality": r"vless:\/\/[^\s\<\>\[\]\{\}\(\)\"\'\`]+?(?:type=reality&.*?host=[^\s&]+.*?sni=[^\s&]+.*?fingerprint=[^\s&]+.*?)?",
        "hysteria": r"hysteria:\/\/" + base_pattern_suffix,
        "hysteria2": r"hysteria2:\/\/" + base_pattern_suffix,
        "tuic": r"tuic:\/\/" + base_pattern_suffix,
        "wireguard": r"wg:\/\/" + base_pattern_suffix,
        "ssh": r"(?:ssh|sftp):\/\/" + base_pattern_suffix,
        "warp": r"(?:warp|cloudflare-warp):\/\/" + base_pattern_suffix,
        "juicity": r"juicity:\/\/" + base_pattern_suffix,
        "mieru": r"mieru:\/\/" + base_pattern_suffix,
        "snell": r"snell:\/\/" + base_pattern_suffix,
        "anytls": r"anytls:\/\/" + base_pattern_suffix,
    }

    for protocol in settings.ACTIVE_PROTOCOLS:
        if protocol in protocol_regex_map:
            patterns[protocol] = protocol_regex_map[protocol]
        else:
            print(f"Warning: No specific regex pattern defined for protocol '{protocol}'. Using generic link pattern.")
            patterns[protocol] = r"\b" + re.escape(protocol) + r":\/\/" + base_pattern_suffix

    return patterns

class TelegramCollector:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=settings.COLLECTION_TIMEOUT_SECONDS)
        self.config_patterns = get_config_regex_patterns()
        print("TelegramCollector: Initialized for Telegram Web (t.me/s/) collection.")

    async def _fetch_channel_page(self, channel_username):
        """Fetches the HTML content of a Telegram Web channel page."""
        # Ensure the username starts with @
        clean_username = channel_username.lstrip('@')
        url = f"https://t.me/s/{clean_username}" # Public Telegram Web URL
        print(f"TelegramCollector: Fetching channel page: {url}")
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9,fa;q=0.8" # Add Persian for better locale matching
            }
            response = await self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status() # Raise HTTPStatusError for bad responses (4xx or 5xx)
            return response.text
        except httpx.TimeoutException:
            print(f"TelegramCollector: Timeout fetching {url}")
            source_manager.update_telegram_channel_score(channel_username, -settings.COLLECTION_TIMEOUT_SECONDS) # Decrease score on timeout
            return None
        except httpx.HTTPStatusError as e:
            # Handle 404 (Not Found), 403 (Forbidden), etc.
            print(f"TelegramCollector: HTTP Error {e.response.status_code} fetching {url}: {e.response.text.strip()[:100]}...")
            if e.response.status_code == 404: # Channel not found
                source_manager.update_telegram_channel_score(channel_username, -100) # Big penalty
                print(f"TelegramCollector: Channel {channel_username} not found. Consider blacklisting.")
            elif e.response.status_code == 429: # Too Many Requests (Rate Limit)
                print(f"TelegramCollector: Rate limit hit for {url}. Consider increasing delay or using proxies.")
                source_manager.update_telegram_channel_score(channel_username, -50) # Big penalty for rate limiting
            else:
                source_manager.update_telegram_channel_score(channel_username, -20) # General HTTP error penalty
            return None
        except httpx.RequestError as e:
            print(f"TelegramCollector: Request error fetching {url}: {e}")
            source_manager.update_telegram_channel_score(channel_username, -15)
            return None
        except Exception as e:
            print(f"TelegramCollector: An unexpected error occurred fetching {url}: {e}")
            source_manager.update_telegram_channel_score(channel_username, -25)
            return None

    def _extract_links_from_text(self, text_content):
        """
        Extracts config links from a given text content using defined regex patterns.
        This is reused from the previous Telethon version.
        """
        found_links = []
        for protocol, pattern in self.config_patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for link in matches:
                found_links.append({'protocol': protocol, 'link': link.strip()})
        return found_links

    def _extract_date_from_message_html(self, message_soup_tag) -> Optional[datetime]:
        """Extracts datetime from a BeautifulSoup message tag."""
        try:
            time_element = message_soup_tag.find('time', class_='time')
            if time_element and 'datetime' in time_element.attrs:
                # '2025-06-27T06:00:00+00:00' format (ISO 8601)
                return datetime.fromisoformat(time_element['datetime'])
        except Exception:
            pass
        return None

    def _is_config_recent(self, message_date: Optional[datetime]) -> bool:
        """Checks if a config message is within the lookback duration."""
        if not message_date:
            # If date cannot be extracted, assume it's recent for now or apply a stricter rule.
            # For this implementation, we'll assume it's valid if date is missing.
            return True
        
        # Ensure message_date is timezone-aware
        if message_date.tzinfo is None:
            message_date = message_date.replace(tzinfo=timezone.utc)

        cutoff_date = datetime.now(timezone.utc) - settings.TELEGRAM_MESSAGE_LOOKBACK_DURATION
        return message_date >= cutoff_date

    async def _discover_and_add_channel(self, raw_channel_input):
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
        collected_links = []
        html_content = await self._fetch_channel_page(channel_username)

        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        # Select messages. Telegram Web uses 'tgme_widget_message_wrap' for the whole message block
        messages_html = soup.find_all('div', class_='tgme_widget_message_wrap')

        if not messages_html:
            print(f"TelegramCollector: No messages found on channel page {channel_username}. Score -1.")
            source_manager.update_telegram_channel_score(channel_username, -1)
            return []

        # Sort messages by date, most recent first (based on 'time' tag)
        # We re-sort because find_all might not return in chronological order
        messages_with_dates = []
        for msg_wrap in messages_html:
            message_text_div = msg_wrap.find('div', class_='tgme_widget_message_text')
            if not message_text_div: continue # Skip if no text content

            msg_date = self._extract_date_from_message_html(msg_wrap)
            messages_with_dates.append((msg_date, message_text_div, msg_wrap))
        
        # Sort by date (most recent first)
        messages_with_dates.sort(key=lambda x: x[0] if x[0] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        processed_message_count = 0
        for msg_date, message_text_div, msg_wrap in messages_with_dates:
            if not self._is_config_recent(msg_date):
                # print(f"TelegramCollector: Skipping old message from {channel_username} dated {msg_date}.")
                continue # Skip messages older than lookback duration

            if settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL is not None and processed_message_count >= settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL:
                print(f"TelegramCollector: Max messages per channel limit ({settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL}) reached for {channel_username}.")
                break # Stop processing if limit reached

            processed_message_count += 1
            
            # Extract text content from various parts of the message HTML
            # This is a simplified approach, a full parser might need to handle nested tags.
            # Find direct text in the message
            main_text = message_text_div.get_text(separator=' ', strip=True)
            links_from_full_text = self._extract_links_from_text(main_text)
            collected_links.extend(links_from_full_text)

            # Look for code blocks (often <pre> or <code> within the message)
            code_blocks = message_text_div.find_all(['pre', 'code'])
            for block in code_blocks:
                block_text = block.get_text(separator=' ', strip=True)
                extracted_from_block = self._extract_links_from_text(block_text)
                collected_links.extend(extracted_from_block)

            # Look for blockquotes (Telegram Web often uses <blockquote> for quotes)
            quotes = message_text_div.find_all('blockquote')
            for quote_tag in quotes:
                quote_text = quote_tag.get_text(separator=' ', strip=True)
                extracted_from_quote = self._extract_links_from_text(quote_text)
                collected_links.extend(extracted_from_quote)

            # --- Discovering new channels from message HTML ---
            if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY:
                # Find links to other Telegram channels (t.me/channelname or @channelname)
                for a_tag in message_text_div.find_all('a', href=True):
                    href = a_tag['href']
                    if 't.me/' in href:
                        await self._discover_and_add_channel(href)
                    elif href.startswith('@'): # Direct @ mention in HTML
                         await self._discover_and_add_channel(href)
                
                # Forwards are harder to detect purely from t.me/s/ HTML without specific IDs/classes for forwarded messages.
                # This might require more advanced HTML parsing if Telegram web changes its structure.
                # The current sample code doesn't directly show a way to detect forwarded channel links easily.
                # We will rely on direct links and mentions for now.


        # Deduplicate links collected from this channel before returning
        collected_links = list({item['link']: item for item in collected_links}.values())

        if not collected_links:
            print(f"TelegramCollector: No config links found in {channel_username} within the specified criteria.")
            source_manager.update_telegram_channel_score(channel_username, -1)
        else:
            print(f"TelegramCollector: Found {len(collected_links)} unique links in {channel_username}.")
            source_manager.update_telegram_channel_score(channel_username, 1) # Positive score for finding configs

        return collected_links

    async def collect_from_telegram(self) -> List[Dict]:
        """Main method to collect from all active Telegram channels."""
        all_collected_links = []
        active_channels = source_manager.get_active_telegram_channels() # Get active and sorted channels

        if not active_channels:
            print("TelegramCollector: No active Telegram channels to process.")
            return []

        # Process channels in parallel (for efficiency)
        tasks = []
        for channel in active_channels:
            # Dynamic delay for web sources could be implemented here based on score
            # For now, relying on httpx timeout and error handling.
            # Add dynamic sleep based on score if needed, similar to Telethon version.
            # current_score = source_manager._all_telegram_scores.get(channel, 0)
            # base_delay = 1 # seconds
            # delay_multiplier = 1 + max(0, -current_score * 0.05) 
            # await asyncio.sleep(base_delay * delay_multiplier) 
            tasks.append(self.collect_from_channel(channel))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            channel = active_channels[i]
            if isinstance(result, Exception):
                print(f"TelegramCollector: Error processing channel {channel}: {result}")
                traceback.print_exc()
                source_manager.update_telegram_channel_score(channel, -15) # Penalize for unhandled errors
            elif result:
                all_collected_links.extend(result)
        
        # Record newly timed-out channels for the report
        for channel_name, data in source_manager.timeout_telegram_channels.items():
            if channel_name in active_channels and source_manager._is_timed_out_telegram_channel(channel_name):
                stats_reporter.add_newly_timed_out_channel(channel_name)

        print(f"TelegramCollector: Finished collection. Total links from Telegram: {len(all_collected_links)}")
        return all_collected_links

    async def close(self):
        """Closes the HTTP client session."""
        await self.client.aclose()
        print("TelegramCollector: HTTP client closed.")

