# src/collectors/web_collector.py

import requests
import re
import os
import json
from src.utils.settings_manager import settings
# برای استفاده مجدد از الگوهای RegEx پروتکل‌ها (get_config_regex_patterns در telegram_collector است)
from src.collectors.telegram_collector import get_config_regex_patterns

class WebLinkCollector:
    def __init__(self):
        self.config_patterns = get_config_regex_patterns()

    def _get_raw_github_url(self, github_url):
        """
        یک URL عادی گیت‌هاب (blob) را به URL محتوای Raw آن تبدیل می‌کند.
        مثال: https://github.com/user/repo/blob/main/file.txt
        تبدیل می‌شود به: https://raw.githubusercontent.com/user/repo/main/file.txt
        """
        if "github.com" in github_url and "/blob/" in github_url:
            raw_url = github_url.replace("github.com", "raw.githubusercontent.com")
            raw_url = raw_url.replace("/blob/", "/")
            return raw_url
        return github_url # اگر URL گیت‌هاب blob قابل تشخیص نبود، همان اصلی را برگردان

    def get_links_from_url(self, url):
        """
        محتوا را از یک URL واکشی کرده و لینک‌های پیکربندی را استخراج می‌کند.
        لینک‌های GitHub blob را به صورت خودکار به Raw تبدیل می‌کند.
        """
        collected_links = []
        final_url = self._get_raw_github_url(url)
        print(f"Fetching content from: {final_url}")

        try:
            # یک محدودیت زمانی برای جلوگیری از گیر کردن اضافه کنید
            response = requests.get(final_url, timeout=settings.COLLECTION_TIMEOUT_SECONDS) # استفاده از تنظیمات
            response.raise_for_status() # برای پاسخ‌های نامناسب (4xx یا 5xx) یک HTTPError ایجاد می‌کند
            content = response.text

            for protocol, pattern in self.config_patterns.items():
                found_links = re.findall(pattern, content, re.IGNORECASE)
                for link in found_links:
                    collected_links.append({'protocol': protocol, 'link': link.strip()})
        except requests.exceptions.Timeout:
            print(f"Error: Timeout after {settings.COLLECTION_TIMEOUT_SECONDS} seconds while fetching {final_url}.")
            # اینجا می توانیم یک سیستم امتیازدهی ساده برای وب سایت ها هم اضافه کنیم
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {final_url}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred with {final_url}: {e}")
        return collected_links

async def main():
    collector = WebLinkCollector()

    # بارگذاری URL وب‌سایت‌ها از settings.WEBSITES_FILE
    websites_file_path = settings.WEBSITES_FILE

    # اگر فایل وجود نداشت، یک فایل خالی ایجاد کن تا ارور ندهد
    if not os.path.exists(websites_file_path):
        print(f"Warning: Websites file not found at {websites_file_path}. Creating an empty one.")
        # مطمئن شوید که دایرکتوری والد هم وجود دارد
        os.makedirs(os.path.dirname(websites_file_path), exist_ok=True)
        with open(websites_file_path, 'w', encoding='utf-8') as f:
            pass # Create empty file

    with open(websites_file_path, 'r', encoding='utf-8') as f:
        target_urls = [line.strip() for line in f if line.strip()]
        # حذف موارد تکراری
        target_urls = list(set(target_urls))

    all_collected_links = []
    if not target_urls:
        print("No website URLs found in sources/websites.txt. Skipping web collection.")
        return [] # اگر لیستی از URLها نبود، لیست خالی برگردان

    for url in target_urls:
        print(f"Processing URL: {url}")
        links = collector.get_links_from_url(url)
        all_collected_links.extend(links)

    print(f"\n--- Web Collection Summary ---")
    print(f"Total unique links collected from web: {len({link['link'] for link in all_collected_links})}")
    print("----------------------------")

    return all_collected_links # لینک‌های جمع‌آوری شده را برگردان

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
