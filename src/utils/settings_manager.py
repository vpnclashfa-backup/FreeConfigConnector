# src/utils/settings_manager.py

import json
import os
from datetime import timedelta

class Settings:
    def __init__(self, config_file='settings/config.json'):
        # مسیر کامل فایل config.json را با توجه به موقعیت فعلی این اسکریپت پیدا می‌کنیم
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # از src/utils به روت پروژه برمی‌گردیم تا به settings/config.json برسیم
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        self.full_config_path = os.path.join(project_root, config_file)

        self.config_data = self._load_config()
        self._set_attributes()

    def _load_config(self):
        """بارگذاری تنظیمات از فایل JSON."""
        if not os.path.exists(self.full_config_path):
            print(f"Error: Configuration file not found at {self.full_config_path}. Please create it as described in the steps.")
            # اگر فایل تنظیمات پیدا نشد، برنامه باید متوقف شود تا کاربر آن را ایجاد کند.
            exit(1)

        try:
            with open(self.full_config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            print(f"Error reading config.json: Invalid JSON format. Please check the file for errors. {e}")
            exit(1)
        except Exception as e:
            print(f"An unexpected error occurred while loading config.json: {e}")
            exit(1)

    def _set_attributes(self):
        """تنظیم ویژگی‌های کلاس Settings از داده‌های بارگذاری شده."""
        # تنظیمات API تلگرام (اولویت با متغیرهای محیطی است)
        # اگر متغیر محیطی وجود داشت، آن را استفاده کن، در غیر این صورت از config.json بخوان
        self.TELEGRAM_API_ID = int(os.environ.get('TELEGRAM_API_ID', self.config_data.get('telegram_api', {}).get('api_id', 0)))
        self.TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH', self.config_data.get('telegram_api', {}).get('api_hash', ''))

        # تنظیمات جمع آوری
        # فیلتر کردن کلیدهای _comment_ از لیست پروتکل‌های فعال
        self.ACTIVE_PROTOCOLS = [
            p for p in self.config_data.get('collection_settings', {}).get('active_protocols', [])
            if not p.startswith('_comment_')
        ]
        self.TELEGRAM_MESSAGE_LOOKBACK_DURATION = timedelta(
            days=self.config_data.get('collection_settings', {}).get('telegram_message_lookback_days', 7)
        )
        # مقدار None در JSON به Python None تبدیل می‌شود
        max_msg_per_channel = self.config_data.get('collection_settings', {}).get('telegram_max_messages_per_channel', 500)
        self.TELEGRAM_MAX_MESSAGES_PER_CHANNEL = None if max_msg_per_channel == "None" else max_msg_per_channel


        # محدودیت‌های پروکسی
        self.MAX_TOTAL_PROXIES = self.config_data.get('proxy_limits', {}).get('max_total_proxies', 1000)
        self.MAX_PROXIES_PER_PROTOCOL = self.config_data.get('proxy_limits', {}).get('max_proxies_per_protocol', {})


        # مسیر فایل‌ها (نسبت به روت پروژه)
        self.SOURCES_DIR_NAME = self.config_data.get('file_paths', {}).get('sources_dir', 'sources')
        self.OUTPUT_DIR_NAME = self.config_data.get('file_paths', {}).get('output_dir', 'output')

        # بازگشت به روت پروژه برای ساخت مسیرهای کامل
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))

        self.CHANNELS_FILE = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('channels_file', 'channels.txt'))
        self.WEBSITES_FILE = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('websites_file', 'websites.txt'))
        self.COLLECTED_LINKS_FILE = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.config_data.get('file_paths', {}).get('collected_links_file', 'collected_links.json'))

# یک نمونه سراسری از کلاس Settings ایجاد می‌کنیم تا سایر ماژول‌ها بتوانند از آن استفاده کنند
settings = Settings()
