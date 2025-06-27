# src/collectors/telegram_collector.py

from telethon.sync import TelegramClient
from telethon.tl.types import Message
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityCode, MessageEntityPre,
    MessageEntitySpoiler, MessageEntityBlockquote, MessageEntityTextUrl,
    MessageEntityMention, MessageEntityMentionName
)
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PeerFloodError, ChannelPrivateError, RPCError, UserDeactivatedBanError, AuthKeyError
import re
import os
import json
from datetime import datetime, timezone
import asyncio 

from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager # وارد کردن SourceManager
from src.utils.stats_reporter import stats_reporter # وارد کردن StatsReporter

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

class TelegramCollector: # تغییر نام به TelegramCollector برای وضوح بیشتر
    def __init__(self, api_id, api_hash, session_name='telegram_session'):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.config_patterns = get_config_regex_patterns()
        # امتیازدهی اکنون توسط source_manager انجام می‌شود، نیازی به channel_scores داخلی نیست.

    async def connect(self):
        print("TelegramCollector: Connecting to Telegram...")
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                print("TelegramCollector: Authorization required. Please enter your phone number and code.")
                await self.client.start()
            print("TelegramCollector: Connected to Telegram.")
        except SessionPasswordNeededError:
            print("TelegramCollector: Error: Two-factor authentication is enabled. Please provide the password.")
            await self.client.disconnect()
            raise # Re-raise to stop if 2FA is needed
        except AuthKeyError:
            print("TelegramCollector: Error: Authorization key is invalid. Please delete the session file and try again.")
            await self.client.disconnect()
            raise
        except Exception as e:
            print(f"TelegramCollector: Failed to connect to Telegram: {e}")
            raise

    async def _extract_links_from_text(self, text_content):
        """
        Extracts config links from a given text content using defined regex patterns.
        """
        found_links = []
        for protocol, pattern in self.config_patterns.items():
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for link in matches:
                found_links.append({'protocol': protocol, 'link': link.strip()})
        return found_links

    async def _discover_and_add_channel(self, raw_channel_input):
        """
        Discovers a new Telegram channel and adds it to the SourceManager if enabled.
        """
        if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY:
            standardized_channel_name = source_manager._standardize_channel_username(raw_channel_input) # استفاده از تابع استانداردسازی در SourceManager
            if standardized_channel_name:
                if source_manager.add_telegram_channel(standardized_channel_name):
                    stats_reporter.increment_discovered_channel_count()
                    print(f"TelegramCollector: Discovered and added new channel: {standardized_channel_name}")
                # else:
                    # print(f"TelegramCollector: Discovered channel {standardized_channel_name} already known or blacklisted.")

    async def collect_from_channel(self, channel_username): # تغییر نام به collect_from_channel
        """
        Collects config links from a specified Telegram channel.
        Includes improvements for error handling, scoring, and parsing various text formats.
        Also discovers new channels from links, mentions, and forwards.
        """
        collected_links = []
        # امتیازدهی اکنون توسط source_manager انجام می‌شود.

        try:
            entity = await self.client.get_entity(channel_username)
            print(f"TelegramCollector: Collecting from channel: {channel_username} (ID: {entity.id})")

            offset_date = datetime.now(timezone.utc) - settings.TELEGRAM_MESSAGE_LOOKBACK_DURATION

            # تأخیر پویا بر اساس امتیاز کانال از source_manager
            current_score = source_manager._all_telegram_scores.get(channel_username, 0)
            # با افزایش امتیاز منفی، تأخیر بیشتر می‌شود (با فرض اینکه امتیاز مثبت خوب است و منفی بد)
            # ما میخواهیم منابع با امتیاز پایین تر کمتر بررسی شوند
            # اینجا تأخیر را بر اساس امتیاز فعلی منبع تنظیم می کنیم. 
            # هرچه امتیاز منفی تر، تأخیر بیشتر.
            # یک ضریب 0.1 برای تأثیرگذاری ملایم تر امتیاز
            base_delay = 1 # ثانیه پایه
            delay_multiplier = 1 + max(0, -current_score * 0.05) # اگر امتیاز منفی شد، ضریب افزایش می یابد

            await asyncio.sleep(base_delay * delay_multiplier) 

            async for message in self.client.iter_messages(
                entity,
                limit=settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL,
                offset_date=offset_date
            ):
                if not message.text:
                    continue

                # 1. بررسی کل متن پیام برای لینک‌های مستقیم
                links_from_full_text = await self._extract_links_from_text(message.text)
                for link_info in links_from_full_text:
                    protocol = link_info.get('protocol', 'unknown')
                    link = link_info.get('link')
                    if link:
                        collected_links.append(link_info) # اضافه کردن دیکشنری
                        stats_reporter.increment_total_collected()
                        stats_reporter.increment_protocol_count(protocol)
                        stats_reporter.record_source_link("telegram", channel_username, protocol)
                        # print(f"  TelegramCollector: Found {protocol} link in full text: {link}")


                # 2. بررسی entityها برای استخراج متن از فرمت‌های خاص (مثلاً کد بلاک)
                if message.entities:
                    for entity in message.entities:
                        start = entity.offset
                        end = entity.offset + entity.length
                        entity_text = message.text[start:end]

                        if isinstance(entity, (MessageEntityCode, MessageEntityPre, MessageEntityBlockquote, MessageEntitySpoiler)):
                            extracted_from_entity = await self._extract_links_from_text(entity_text)
                            for link_info in extracted_from_entity:
                                protocol = link_info.get('protocol', 'unknown')
                                link = link_info.get('link')
                                if link:
                                    collected_links.append(link_info)
                                    stats_reporter.increment_total_collected()
                                    stats_reporter.increment_protocol_count(protocol)
                                    stats_reporter.record_source_link("telegram", channel_username, protocol)
                                    # print(f"  TelegramCollector: Found {protocol} link in entity ({type(entity).__name__}): {link}")

                        # --- کشف کانال‌های جدید از لینک‌ها/تگ‌ها در پیام‌های تلگرام ---
                        # کشف کانال از MessageEntityTextUrl (لینک مستقیم به t.me)
                        if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY and isinstance(entity, MessageEntityTextUrl):
                            if "t.me/" in entity.url:
                                await self._discover_and_add_channel(entity.url)

                        # کشف کانال از MessageEntityMention (تگ @)
                        elif settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY and isinstance(entity, (MessageEntityMention, MessageEntityMentionName)):
                            if isinstance(entity, MessageEntityMention):
                                await self._discover_and_add_channel(entity_text)
                            elif isinstance(entity, MessageEntityMentionName) and entity.user and entity.user.username:
                                await self._discover_and_add_channel("@" + entity.user.username)

                # --- کشف کانال‌های جدید از پیام‌های فوروارد شده ---
                if settings.ENABLE_TELEGRAM_CHANNEL_DISCOVERY and message.fwd_from and message.fwd_from.from_id:
                    fwd_from = message.fwd_from.from_id
                    if hasattr(fwd_from, 'channel_id'): # اگر از یک کانال فوروارد شده باشد
                        try:
                            forwarded_channel_entity = await self.client.get_entity(fwd_from.channel_id)
                            if hasattr(forwarded_channel_entity, 'username') and forwarded_channel_entity.username:
                                await self._discover_and_add_channel("@" + forwarded_channel_entity.username)
                        except Exception as e:
                            print(f"TelegramCollector: Could not get entity for forwarded channel ID {fwd_from.channel_id}: {e}")

            # حذف لینک‌های تکراری در این مرحله برای هر کانال
            # توجه: این لینک‌ها دیکشنری هستند، پس بر اساس 'link' فیلتر می‌کنیم
            collected_links = list({item['link']: item for item in collected_links}.values())

            if not collected_links:
                print(f"TelegramCollector: No config links found in {channel_username} within the specified criteria.")
                source_manager.update_telegram_channel_score(channel_username, -1) # امتیاز منفی برای عدم یافتن کانفیگ
            else:
                print(f"TelegramCollector: Found {len(collected_links)} unique links in {channel_username}.")
                source_manager.update_telegram_channel_score(channel_username, 1) # امتیاز مثبت برای یافتن کانفیگ

        except FloodWaitError as e:
            wait_time = e.seconds
            print(f"TelegramCollector: Warning: Flood wait of {wait_time} seconds encountered for {channel_username}. Waiting...")
            await asyncio.sleep(wait_time + base_delay * delay_multiplier) # تأخیر بیشتر بر اساس فلود و امتیاز
            source_manager.update_telegram_channel_score(channel_username, -5) # امتیاز منفی شدید برای فلود
            print(f"TelegramCollector: Resuming collection for {channel_username} after wait.")
        except PeerFloodError:
            print(f"TelegramCollector: Warning: Peer Flood encountered for {channel_username}. Skipping for now.")
            source_manager.update_telegram_channel_score(channel_username, -10) # امتیاز منفی بسیار شدید
        except ChannelPrivateError:
            print(f"TelegramCollector: Error: Channel {channel_username} is private or inaccessible. Skipping.")
            source_manager.update_telegram_channel_score(channel_username, -2) # امتیاز منفی
        except (UserDeactivatedBanError, AuthKeyError) as e:
            print(f"TelegramCollector: Critical Error for {channel_username}: {e}. Account might be banned or key invalid. Exiting collector.")
            raise # یک خطای بحرانی که باید جمع آوری تلگرام را متوقف کند
        except RPCError as e:
            print(f"TelegramCollector: An RPC error occurred for {channel_username}: {e}. Skipping this channel.")
            source_manager.update_telegram_channel_score(channel_username, -3) # امتیاز منفی
        except Exception as e:
            print(f"TelegramCollector: An unexpected error occurred while collecting from {channel_username}: {e}. Skipping this channel.")
            source_manager.update_telegram_channel_score(channel_username, -1) # امتیاز منفی

        return collected_links


    async def collect_from_telegram(self): # تغییر نام به collect_from_telegram
        """Main method to collect from all active Telegram channels."""
        all_collected_links = []
        active_channels = source_manager.get_active_telegram_channels() # دریافت کانال‌های فعال و مرتب شده
        print(f"\nTelegramCollector: Starting collection from {len(active_channels)} active Telegram channels.")

        if not active_channels:
            print("TelegramCollector: No active Telegram channels to process.")
            return []

        for channel in active_channels:
            print(f"TelegramCollector: Processing channel: {channel}")
            # اجرای جمع آوری لینک‌ها و افزودن به لیست
            collected_for_channel = await self.collect_from_channel(channel)
            all_collected_links.extend(collected_for_channel)
            # تأخیر بین پردازش هر کانال اکنون با توجه به امتیاز در collect_from_channel مدیریت می‌شود

        # ثبت کانال‌های تازه تایم‌اوت شده برای گزارش
        for channel_name, data in source_manager.timeout_telegram_channels.items():
            # اگر این کانال در ابتدا فعال بوده و حالا تایم‌اوت شده است
            if channel_name in active_channels and source_manager._is_timed_out_telegram_channel(channel_name):
                 stats_reporter.add_newly_timed_out_channel(channel_name)

        print(f"TelegramCollector: Finished collection. Total links from Telegram: {len(all_collected_links)}")
        return all_collected_links

    async def close(self): # اضافه کردن متد close
        print("TelegramCollector: Disconnecting from Telegram.")
        await self.client.disconnect()
