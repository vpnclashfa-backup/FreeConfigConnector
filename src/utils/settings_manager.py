# src/utils/settings_manager.py

import json
import os
from datetime import timedelta
from typing import Optional, Dict # Added Dict

class Settings:
    def __init__(self, config_file: str = 'settings/config.json'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
        self.full_config_path = os.path.join(project_root, config_file)

        self.config_data = self._load_config()
        self._set_attributes()

    def _load_config(self) -> Dict:
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
        # Collection settings
        self.ACTIVE_PROTOCOLS: List[str] = [ # Explicitly typed
            p for p in self.config_data.get('collection_settings', {}).get('active_protocols', [])
            # if not p.startswith('_comment_') # Removed comments from JSON, so this filter is not strictly needed
        ]
        self.TELEGRAM_MESSAGE_LOOKBACK_DURATION = timedelta(
            days=self.config_data.get('collection_settings', {}).get('telegram_message_lookback_days', 7)
        )
        max_msg_per_channel: Optional[int] = self.config_data.get('collection_settings', {}).get('telegram_max_messages_per_channel', 500)
        self.TELEGRAM_MAX_MESSAGES_PER_CHANNEL = None if max_msg_per_channel == "None" else max_msg_per_channel
        
        self.COLLECTION_TIMEOUT_SECONDS = self.config_data.get('collection_settings', {}).get('collection_timeout_seconds', 15)


        # Parser Settings
        self.ENABLE_BASE64_DECODING: bool = self.config_data.get('parser_settings', {}).get('enable_base64_decoding', True)
        self.ENABLE_CLASH_PARSER: bool = self.config_data.get('parser_settings', {}).get('enable_clash_parser', True)
        self.ENABLE_SINGBOX_PARSER: bool = self.config_data.get('parser_settings', {}).get('enable_singbox_parser', True)
        self.ENABLE_JSON_PARSER: bool = self.config_data.get('parser_settings', {}).get('enable_json_parser', True)
        self.IGNORE_UNPARSEABLE_CONTENT: bool = self.config_data.get('parser_settings', {}).get('ignore_unparseable_content', False)


        # Discovery Settings
        self.ENABLE_TELEGRAM_CHANNEL_DISCOVERY: bool = self.config_data.get('discovery_settings', {}).get('enable_telegram_channel_discovery', True)
        self.ENABLE_CONFIG_LINK_DISCOVERY: bool = self.config_data.get('discovery_settings', {}).get('enable_config_link_discovery', True)
        self.MAX_DISCOVERED_SOURCES_TO_ADD: int = self.config_data.get('discovery_settings', {}).get('max_discovered_sources_to_add', 50)


        # Source Management Settings
        self.MAX_TIMEOUT_SCORE_TELEGRAM: int = self.config_data.get('source_management', {}).get('max_timeout_score_telegram', -50)
        self.MAX_TIMEOUT_SCORE_WEB: int = self.config_data.get('source_management', {}).get('max_timeout_score_web', -10)
        self.TIMEOUT_RECOVERY_DURATION: timedelta = timedelta(
            days=self.config_data.get('source_management', {}).get('timeout_recovery_duration_days', 30)
        )
        self.BLACKLIST_TELEGRAM_CHANNELS: List[str] = self.config_data.get('source_management', {}).get('blacklist_telegram_channels', [])
        self.BLACKLIST_WEBSITES: List[str] = self.config_data.get('source_management', {}).get('blacklist_websites', [])
        self.WHITELIST_TELEGRAM_CHANNELS: List[str] = self.config_data.get('source_management', {}).get('whitelist_telegram_channels', [])
        self.WHITELIST_WEBSITES: List[str] = self.config_data.get('source_management', {}).get('whitelist_websites', [])


        # Proxy Limits
        self.MAX_TOTAL_PROXIES: int = self.config_data.get('proxy_limits', {}).get('max_total_proxies', 1000)
        self.MAX_PROXIES_PER_PROTOCOL: Dict[str, int] = self.config_data.get('proxy_limits', {}).get('max_proxies_per_protocol', {})


        # File Paths
        self.SOURCES_DIR_NAME: str = self.config_data.get('file_paths', {}).get('sources_dir', 'sources')
        self.OUTPUT_DIR_NAME: str = self.config_data.get('file_paths', {}).get('output_dir', 'output')
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))

        self.CHANNELS_FILE: str = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('channels_file', 'channels.txt'))
        self.WEBSITES_FILE: str = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('websites_file', 'websites.txt'))
        self.COLLECTED_LINKS_FILE: str = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.config_data.get('file_paths', {}).get('collected_links_file', 'collected_links.json'))
        
        self.DISCOVERED_TELEGRAM_CHANNELS_FILE: str = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('discovered_telegram_channels_file', 'discovered_telegram_channels.txt'))
        self.DISCOVERED_WEBSITES_FILE: str = os.path.join(self.PROJECT_ROOT, self.SOURCES_DIR_NAME, self.config_data.get('file_paths', {}).get('discovered_websites_file', 'discovered_websites.txt'))
        self.TIMEOUT_TELEGRAM_CHANNELS_FILE: str = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.config_data.get('file_paths', {}).get('timeout_telegram_channels_file', 'timeout_telegram_channels.json'))
        self.TIMEOUT_WEBSITES_FILE: str = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.config_data.get('file_paths', {}).get('timeout_websites_file', 'timeout_websites.json'))

        # مسیرهای خروجی سابسکریپشن
        self.SUB_DIR_NAME: str = self.config_data.get('file_paths', {}).get('sub_dir', 'subs')
        self.FULL_SUB_DIR_PATH: str = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.SUB_DIR_NAME)

        self.BASE64_SUB_FILE: str = os.path.join(self.FULL_SUB_DIR_PATH, self.config_data.get('file_paths', {}).get('base64_sub_file', 'base64/base64_links.txt'))
        self.PLAINTEXT_SUB_FILE: str = os.path.join(self.FULL_SUB_DIR_PATH, self.config_data.get('file_paths', {}).get('plaintext_sub_file', 'plaintext/plaintext_links.txt'))
        self.MIXED_PROTOCOLS_SUB_FILE: str = os.path.join(self.FULL_SUB_DIR_PATH, self.config_data.get('file_paths', {}).get('mixed_protocols_sub_file', 'mixed/mixed_links.txt'))
        
        # تنظیمات خروجی
        self.PROTOCOLS_FOR_MIXED_OUTPUT: List[str] = [
            p for p in self.config_data.get('output_settings', {}).get('protocols_for_mixed_output', [])
            # if not p.startswith('_comment_') # Removed comments from JSON
        ]
        self.OUTPUT_HEADER_BASE64_ENABLED: bool = self.config_data.get('output_settings', {}).get('output_header_base64_enabled', True)
        self.GENERATE_PROTOCOL_SPECIFIC_FILES: bool = self.config_data.get('output_settings', {}).get('generate_protocol_specific_files', True)
        self.PROTOCOL_SPECIFIC_DIR_NAME: str = self.config_data.get('output_settings', {}).get('protocol_specific_dir', 'protocols')
        self.FULL_PROTOCOL_SPECIFIC_DIR_PATH: str = os.path.join(self.FULL_SUB_DIR_PATH, self.PROTOCOL_SPECIFIC_DIR_NAME)

        # مسیر فایل گزارش
        self.REPORT_FILE: str = os.path.join(self.PROJECT_ROOT, self.OUTPUT_DIR_NAME, self.config_data.get('file_paths', {}).get('report_file', 'report.md'))


settings = Settings()
