# src/utils/output_manager.py

import os
import base64
from typing import List, Dict
from src.utils.settings_manager import settings

class OutputManager:
    def __init__(self):
        # Ensure output and subs directories exist
        # اطمینان از وجود پوشه‌های خروجی اصلی
        os.makedirs(settings.FULL_SUB_DIR_PATH, exist_ok=True)
        # Create sub-directories for base64, plaintext, and mixed based on their file paths
        # ایجاد زیرپوشه‌های مخصوص برای هر نوع خروجی
        os.makedirs(os.path.dirname(settings.BASE64_SUB_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(settings.PLAINTEXT_SUB_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(settings.MIXED_PROTOCOLS_SUB_FILE), exist_ok=True)
        print("OutputManager: Output directories ensured.")

    def save_configs(self, unique_links: List[Dict]):
        """
        Saves collected unique links into structured output files (Base64, Plaintext, Mixed).
        لینک‌های منحصر به فرد جمع‌آوری شده را در فایل‌های خروجی ساختاریافته (بیس۶۴، متن ساده، ترکیبی) ذخیره می‌کند.
        """
        print("\nOutputManager: Saving collected configs...")
        
        plaintext_links = []
        base64_links_to_encode = [] # Links that will be base64 encoded for the file
        mixed_output_links = [] # Links for the mixed file

        for link_info in unique_links:
            protocol = link_info.get('protocol')
            link = link_info.get('link')

            if not protocol or not link:
                continue

            # Add to plaintext file
            plaintext_links.append(link)

            # Add to base64 encoding list
            base64_links_to_encode.append(link)

            # Add to mixed output file based on settings
            # افزودن به فایل خروجی ترکیبی بر اساس تنظیمات
            if settings.PROTOCOLS_FOR_MIXED_OUTPUT: # If specific protocols are defined for mixed output
                if protocol in settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                    mixed_output_links.append(link)
            else: # If no specific protocols are defined, include all active protocols in mixed output
                if protocol in settings.ACTIVE_PROTOCOLS:
                    mixed_output_links.append(link)
        
        # Sort links alphabetically for consistency
        # مرتب‌سازی لینک‌ها بر اساس حروف الفبا برای ثبات
        plaintext_links.sort()
        base64_links_to_encode.sort()
        mixed_output_links.sort()

        # Save Plaintext File
        self._write_plaintext_file(settings.PLAINTEXT_SUB_FILE, plaintext_links)

        # Save Base64 File
        self._write_base64_file(settings.BASE64_SUB_FILE, base64_links_to_encode)

        # Save Mixed Protocols File
        self._write_plaintext_file(settings.MIXED_PROTOCOLS_SUB_FILE, mixed_output_links)

        print("OutputManager: All configs saved to respective files.")

    def _write_plaintext_file(self, file_path: str, links: List[str]):
        """
        Writes a list of links to a file, each on a new line.
        لیستی از لینک‌ها را در یک فایل، هر لینک در یک خط جدید، می‌نویسد.
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
            with open(file_path, 'w', encoding='utf-8') as f:
                for link in links:
                    f.write(link + '\n')
            print(f"OutputManager: Saved {len(links)} plaintext links to {file_path}")
        except Exception as e:
            print(f"OutputManager: Error saving plaintext links to {file_path}: {e}")

    def _write_base64_file(self, file_path: str, links: List[str]):
        """
        Encodes a list of links to base64 and writes them to a file.
        Includes a header if enabled in settings.
        لیستی از لینک‌ها را به بیس۶۴ کدگذاری کرده و در یک فایل می‌نویسد.
        اگر در تنظیمات فعال باشد، شامل یک هدر نیز می‌شود.
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
            concatenated_links = "\n".join(links)
            encoded_bytes = base64.b64encode(concatenated_links.encode('utf-8'))
            encoded_string = encoded_bytes.decode('utf-8')

            with open(file_path, 'w', encoding='utf-8') as f:
                if settings.OUTPUT_HEADER_BASE64_ENABLED:
                    # This header is specific to some clients for subscriptions
                    # Example: profile-title, profile-update-interval, etc.
                    # این هدر برای برخی از کلاینت‌ها جهت اشتراک‌ها استفاده می‌شود.
                    # شما می‌توانید این هدر را بر اساس نیاز خود سفارشی کنید.
                    header_template = """//profile-title: base64:{}
//profile-update-interval: 1
//subscription-userinfo: upload=0; download=0; total=10737418240000000; expire=2546249531
//support-url: https://t.me/your_support_channel # Replace with your actual support channel
//profile-web-page-url: https://github.com/your_repo # Replace with your actual repo
"""
                    # Encode a default title or customize it
                    default_title = "My-Config-Subscription"
                    encoded_title = base64.b64encode(default_title.encode('utf-8')).decode('utf-8')
                    f.write(header_template.format(encoded_title) + "\n")

                f.write(encoded_string)
            print(f"OutputManager: Saved {len(links)} base64 encoded links to {file_path}")
        except Exception as e:
            print(f"OutputManager: Error saving base64 links to {file_path}: {e}")

# Create a global instance of OutputManager
# یک نمونه سراسری از OutputManager ایجاد می‌کنیم
output_manager = OutputManager()
