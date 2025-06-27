# src/collectors/telegram_collector.py

from telethon.sync import TelegramClient
from telethon.tl.types import Message
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PeerFloodError, ChannelPrivateError, RPCError
import re
import os
import json
from datetime import datetime, timezone
import asyncio # نیاز است چون از await و async استفاده می کنیم

# Import settings from our custom settings manager
from src.utils.settings_manager import settings

# این تابع الگوهای RegEx را برای پروتکل‌های مختلف VPN/پروکسی تعریف می‌کند.
def get_config_regex_patterns():
    patterns = {}
    base_pattern_suffix = r"[^\s\<\>\[\]\{\}\(\)\"\'\`]+"

    # نقشه جامع پروتکل‌ها به الگوهای RegEx خاص آن‌ها
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
        self.channel_scores = {} # برای ردیابی امتیاز کانال‌ها

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
            # You might want to prompt the user for password here or handle it.
            await self.client.disconnect()
            raise
        except Exception as e:
            print(f"Failed to connect to Telegram: {e}")
            raise

    async def get_links_from_channel(self, channel_username):
        """
        لینک‌های پیکربندی را از یک کانال تلگرام مشخص جمع‌آوری می‌کند.
        شامل بهبودهایی برای مدیریت خطا و امتیازدهی به کانال‌ها.
        """
        collected_links = []
        self.channel_scores[channel_username] = self.channel_scores.get(channel_username, 0) # امتیاز اولیه

        try:
            entity = await self.client.get_entity(channel_username)
            print(f"Collecting from channel: {channel_username} (ID: {entity.id})")

            offset_date = datetime.now(timezone.utc) - settings.TELEGRAM_MESSAGE_LOOKBACK_DURATION

            # تنظیم اولیه تأخیر برای هر کانال (با توجه به بهبود هوشمند)
            initial_delay = 1 # ثانیه
            current_delay = initial_delay * (1 + self.channel_scores[channel_username] * 0.1) # با افزایش امتیاز منفی، تأخیر بیشتر می‌شود

            async for message in self.client.iter_messages(
                entity,
                limit=settings.TELEGRAM_MAX_MESSAGES_PER_CHANNEL,
                offset_date=offset_date
            ):
                if message.text:
                    found_in_message = False
                    for protocol, pattern in self.config_patterns.items():
                        found_links = re.findall(pattern, message.text, re.IGNORECASE)
                        for link in found_links:
                            collected_links.append({'protocol': protocol, 'link': link.strip()})
                            found_in_message = True

                    # اگر در یک پیام، هیچ لینکی پیدا نشد، ممکن است نشان‌دهنده محتوای نامربوط باشد
                    # این بخش را فعلاً برای سادگی پیچیده نمی‌کنیم، اما می‌توان آن را هوشمندتر کرد.

            if not collected_links:
                print(f"No config links found in {channel_username} within the specified criteria.")
                self.channel_scores[channel_username] -= 1 # امتیاز منفی برای عدم یافتن کانفیگ
            else:
                print(f"Found {len(collected_links)} links in {channel_username}.")
                self.channel_scores[channel_username] += 1 # امتیاز مثبت برای یافتن کانفیگ

        except FloodWaitError as e:
            print(f"Warning: Flood wait of {e.seconds} seconds encountered for {channel_username}. Waiting...")
            await asyncio.sleep(e.seconds + current_delay) # اضافه کردن تأخیر بیشتر
            self.channel_scores[channel_username] -= 5 # امتیاز منفی شدید برای فلود
            print(f"Resuming collection for {channel_username} after wait.")
            # اگر خواستید می‌توانید دوباره همین کانال را فراخوانی کنید
            # return await self.get_links_from_channel(channel_username)
        except PeerFloodError:
            print(f"Warning: Peer Flood encountered for {channel_username}. Skipping for now.")
            self.channel_scores[channel_username] -= 10 # امتیاز منفی بسیار شدید
        except ChannelPrivateError:
            print(f"Error: Channel {channel_username} is private or inaccessible. Skipping.")
            self.channel_scores[channel_username] -= 2 # امتیاز منفی
        except RPCError as e:
            print(f"An RPC error occurred for {channel_username}: {e}. Skipping this channel.")
            self.channel_scores[channel_username] -= 3 # امتیاز منفی
        except Exception as e:
            print(f"An unexpected error occurred while collecting from {channel_username}: {e}. Skipping this channel.")
            self.channel_scores[channel_username] -= 1 # امتیاز منفی

        # در هر صورت، حتی اگر خطا رخ داد، لیست لینک‌های جمع‌آوری شده تا آن لحظه را برگردان
        # یا در صورت خطا، لیست خالی برگردان
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
    except Exception: # اگر اتصال موفقیت آمیز نبود، از تابع خارج می‌شویم
        return []

    channels_file_path = settings.CHANNELS_FILE
    if not os.path.exists(channels_file_path):
        print(f"Error: Channels file not found at {channels_file_path}. Please create it and add channel usernames.")
        return []

    with open(channels_file_path, 'r', encoding='utf-8') as f:
        raw_channels = [line.strip() for line in f if line.strip()]
        target_channels = [standardize_channel_username(ch) for ch in raw_channels]
        target_channels = list(set(target_channels)) # حذف موارد تکراری

    all_collected_links = []
    for channel in target_channels:
        print(f"Processing channel: {channel}")
        # اجرای جمع آوری لینک‌ها و افزودن به لیست
        collected_for_channel = await collector.get_links_from_channel(channel)
        all_collected_links.extend(collected_for_channel)
        # یک تأخیر کوتاه بین کانال‌ها برای کاهش احتمال FloodWait
        await asyncio.sleep(1) # 1 ثانیه تأخیر بین پردازش هر کانال

    await collector.disconnect()

    return all_collected_links # بازگرداندن لینک‌های جمع‌آوری شده

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
