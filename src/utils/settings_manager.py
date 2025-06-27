# src/utils/settings_manager.py

import json
import os
from datetime import timedelta

class Settings:
    def __init__(self, config_file='settings/config.json'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        self.full_config_path = os.path.join(project_root, config_file)

        self.config_data = self._load_config()
        self._set_attributes()

    def _load_config(self):
        if not os.path.exists(self.full_config_path):
            print(f"Error: Configuration file not found at {self.full_config_path}. Please create it as described in the steps.")
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
        # Telegram API settings (prioritize environment variables)
        self.TELEGRAM_API_ID = int(os.environ.get('TELEGRAM_API_ID', self.config_data.get('telegram_api', {}).get('api_id', 0)))
        self.TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH', self.config_data.get('telegram_api', {}).get('api_hash', ''))

        # Collection settings
        self.ACTIVE_PROTOCOLS = [
            p for p in self.config_data.get('collection_settings', {}).get('active_protocols', [])
            if not p.startswith('_comment_')
        ]
        self.TELEGRAM_MESSAGE_LOOKBACK_DURATION = timedelta(
            days=self.config_data.get('collection_settings', {}).get('telegram_message_lookback_days', 7)
        )
        max_msg_per_channel = self.config_data.get('collection_settings', {}).get('telegram_max_messages_per_channel', 500)
        self.TELEGRAM_MAX_MESSAGES_PER_CHANNEL = None if max_msg_per_channel == "None" else max_msg_per_channel

        # --- جدید: تنظیمات تایم‌اوت ---
        self.COLLECTION_TIMEOUT_SECONDS = self.config_data.get('collection_settings', {}).get('collection_timeout_seconds', 15)


        # Parser Settings --- جدید: تنظیمات پارسر ---
        self.ENABLE_BASE64_DECODING = self.config_data.get('parser_settings', {}).get('enable_base64_decoding', True)
        self.ENABLE_CLASH_PARSER = self.config_data.get('parser_settings', {}).get('enable_clash_parser', True)
        self.ENABLE_SINGBOX_PARSER = self.config_data.get('parser_settings', {}).get('enable_singbox_parser', True)
        self.ENABLE_JSON_PARSER = self.config_data.get('parser_settings', {}).get('enable_json_parser', True)
        self.IGNORE_UNPARSEABLE_CONTENT = self.config_data.get('parser_settings', {}).get('ignore_unparseable_content', False)


        # Proxy Limits
        self.MAX_TOTAL_PROXIES = self.config_data.get('proxy_limits', {}).get('max_total_proxies', 1000)
        self.MAX_PROXIES_PER_PROTOCOL = self.config_data.get('proxy_limits', {}).get('max_proxies_per_protocol', {})


        # File Paths
        self.SOURCES_DIR_NAME = self.config_data.get('file_paths', {}).get('sources_dir', 'sources')
        self.OUTPUT_DIR_NAME = self.config_data.get('file_paths', {}).get('output_dir', 'output')

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))

        self.CHANNELS_FILE = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('channels_file', 'channels.txt'))
        self.WEBSITES_FILE = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('websites_file', 'websites.txt'))
        self.COLLECTED_LINKS_FILE = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.config_data.get('file_paths', {}).get('collected_links_file', 'collected_links.json'))

settings = Settings()
