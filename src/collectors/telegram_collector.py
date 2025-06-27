# src/collectors/telegram_collector.py

from telethon.sync import TelegramClient
from telethon.tl.types import Message
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityUnderline,
    MessageEntityStrike, MessageEntityCode, MessageEntityPre,
    MessageEntitySpoiler, MessageEntityBlockquote, MessageEntityCustomEmoji,
    MessageEntityTextUrl, MessageEntityMention, MessageEntityHashtag,
    MessageEntityCashtag, MessageEntityBotCommand, MessageEntityEmail,
    MessageEntityUrl, MessageEntityPhoneNumber, MessageEntityMentionName,
    MessageEntityBankCard, MessageEntityPhone, MessageEntityEmail
)
import re
import os
import json
from datetime import datetime, timezone
import asyncio 

from src.utils.settings_manager import settings

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

class TelegramLinkCollector:
    def __init__(self, api_id, api_hash, session_name='telegram_session'):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.config_patterns = get_config_regex_patterns()
        self.channel_scores = {}

    async def connect(self):
        print("Connecting to Telegram...")
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                print("Authorization required. Please enter your phone number and code.")
                await self.client.start()
            print("Connected to Telegram.")
        except SessionPasswordNeededError:
            print("Error: Two-factor authentication is enabled. Please provide the password.")
            await self.client.disconnect()
            raise
        except Exception as e:
            print(f"Failed to connect to Telegram: {e}")
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

    async def get_links_from_channel(self, channel_username):
        """
        لینک‌های پیکربندی را از یک کانال تلگرام مشخص جمع‌آوری می‌کند.
        شامل بهبودهایی برای مدیریت خطا و امتیازدهی به کانال‌ها.
        همچنین انواع فرمت‌های متنی (مثل کد بلاک) را بررسی می‌کند.
        """
        collected_links = []
        self.channel_scores[channel_username] = self.channel_scores.get(channel_username, 0)

        try:
            entity = await self.client.get_entity(channel_username)
            print(f"Collecting from channel: {channel_username} (ID: {entity.id})")

            offset_date = datetime.now(timezone.utc) - settings.TELEGRAM_MESSAGE_LOOKBACK_DURATION

            initial_delay = 1 # ثانیه
            current_delay = initial_delay * (1 + self.channel_scores[channel_username] * 0.1)

            async for message in self.client.iter_messages(
                entity,
                limit=settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL,
                offset_date=offset_date
            ):
                if not message.text:
                    continue # اگر پیام متنی نداشت، رد شو

                # 1. ابتدا کل متن پیام را بررسی کن
                links_from_full_text = await self._extract_links_from_text(message.text)
                collected_links.extend(links_from_full_text)

                # 2. بررسی entityها برای استخراج متن از فرمت‌های خاص (مثلاً کد بلاک)
                if message.entities:
                    for entity in message.entities:
                        start = entity.offset
                        end = entity.offset + entity.length
                        entity_text = message.text[start:end]

                        # انواع مختلف MessageEntity برای قالب‌بندی‌های خاص
                        if isinstance(entity, (MessageEntityCode, MessageEntityPre, MessageEntityBlockquote, MessageEntitySpoiler)):
                            # این فرمت‌ها معمولاً محتوای کانفیگ را به صورت خام نگه می‌دارند
                            extracted_from_entity = await self._extract_links_from_text(entity_text)
                            collected_links.extend(extracted_from_entity)

                        # برای انواع دیگر مثل Bold, Italic, Underline, Strikethrough، متن همچنان بخشی از message.text است
                        # و توسط بررسی اولیه پوشش داده می‌شود.
                        # اگر نیاز بود، می‌توانیم برای اینها هم منطق خاصی اضافه کنیم.
                        # مثال: MessageEntityBold, MessageEntityItalic, MessageEntityUnderline, MessageEntityStrike
                        # MessageEntityTextUrl (اگر لینک داخل خودش یک کانفیگ باشد)

            # حذف لینک‌های تکراری در این مرحله برای هر کانال
            collected_links = list({link['link']: link for link in collected_links}.values())

            if not collected_links:
                print(f"No config links found in {channel_username} within the specified criteria.")
                self.channel_scores[channel_username] -= 1
            else:
                print(f"Found {len(collected_links)} links in {channel_username}.")
                self.channel_scores[channel_username] += 1

        except FloodWaitError as e:
            print(f"Warning: Flood wait of {e.seconds} seconds encountered for {channel_username}. Waiting...")
            await asyncio.sleep(e.seconds + current_delay)
            self.channel_scores[channel_username] -= 5
            print(f"Resuming collection for {channel_username} after wait.")
        except PeerFloodError:
            print(f"Warning: Peer Flood encountered for {channel_username}. Skipping for now.")
            self.channel_scores[channel_username] -= 10
        except ChannelPrivateError:
            print(f"Error: Channel {channel_username} is private or inaccessible. Skipping.")
            self.channel_scores[channel_username] -= 2
        except RPCError as e:
            print(f"An RPC error occurred for {channel_username}: {e}. Skipping this channel.")
            self.channel_scores[channel_username] -= 3
        except Exception as e:
            print(f"An unexpected error occurred while collecting from {channel_username}: {e}. Skipping this channel.")
            self.channel_scores[channel_username] -= 1

        return collected_links


    async def disconnect(self):
        print("Disconnecting from Telegram.")
        await self.client.disconnect()

def standardize_channel_username(raw_input):
    """
    فرمت‌های مختلف ورودی کانال تلگرام را به فرمت استاندارد @username تبدیل می‌کند.
    """
    username = raw_input.replace('https://t.me/s/', '').replace('https://t.me/', '').replace('t.me/s/', '').replace('t.me/', '')
    if username.endswith('@'):
        username = username[:-1]
    if not username.startswith('@'):
        username = '@' + username
    return username.strip()


async def main():
    API_ID = settings.TELEGRAM_API_ID
    API_HASH = settings.TELEGRAM_API_HASH

    if not API_ID or not API_HASH:
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH are not set in environment variables or settings/config.json.")
        print("Please set them before running the script. You can get them from my.telegram.org.")
        return []

    collector = TelegramLinkCollector(API_ID, API_HASH)

    try:
        await collector.connect()
    except Exception:
        return []

    channels_file_path = settings.CHANNELS_FILE
    if not os.path.exists(channels_file_path):
        print(f"Error: Channels file not found at {channels_file_path}. Please create it and add channel usernames.")
        return []

    with open(channels_file_path, 'r', encoding='utf-8') as f:
        raw_channels = [line.strip() for line in f if line.strip()]
        target_channels = [standardize_channel_username(ch) for ch in raw_channels]
        target_channels = list(set(target_channels))

    all_collected_links = []
    for channel in target_channels:
        print(f"Processing channel: {channel}")
        collected_for_channel = await collector.get_links_from_channel(channel)
        all_collected_links.extend(collected_for_channel)
        await asyncio.sleep(1)

    await collector.disconnect()

    return all_collected_links

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
