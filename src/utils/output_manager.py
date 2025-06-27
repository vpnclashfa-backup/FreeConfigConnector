# src/utils/output_manager.py

import os
import base64
from typing import List, Dict
from collections import defaultdict # New: To group links by protocol
from src.utils.settings_manager import settings

class OutputManager:
    def __init__(self):
        # Ensure base output and subs directories exist
        # اطمینان از وجود پوشه‌های خروجی اصلی
        os.makedirs(settings.FULL_SUB_DIR_PATH, exist_ok=True)
        
        # Ensure plaintext and base64 main directories exist
        # اطمینان از وجود پوشه‌های اصلی Plaintext و Base64
        os.makedirs(settings.FULL_PLAINTEXT_OUTPUT_PATH, exist_ok=True)
        os.makedirs(settings.FULL_BASE64_OUTPUT_PATH, exist_ok=True)

        # Create protocol-specific sub-directories within both plaintext and base64
        # ایجاد زیرپوشه‌های پروتکل-خاص در داخل پوشه‌های Plaintext و Base64
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            os.makedirs(settings.FULL_PLAINTEXT_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
            os.makedirs(settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
            print(f"OutputManager: Protocol-specific directories ensured under plaintext/ and base64/.")
        
        # Mixed file directories are implicitly created when writing the file.

        print("OutputManager: Core output directories for new structure ensured.")


    def save_configs(self, unique_links: List[Dict]):
        """
        Saves collected unique links into the new structured output files.
        لینک‌های منحصر به فرد جمع‌آوری شده را در فایل‌های خروجی ساختاریافته جدید ذخیره می‌کند.
        """
        print("\nOutputManager: Saving collected configs to new structure...")
        
        # NEW: These lists now directly represent the content for the mixed files
        mixed_links_plaintext: List[str] = [] 
        mixed_links_base64: List[str] = []    # This list will be encoded later

        protocol_specific_links_plaintext: Dict[str, List[str]] = defaultdict(list)
        protocol_specific_links_base64: Dict[str, List[str]] = defaultdict(list)
        
        for link_info in unique_links:
            protocol = link_info.get('protocol')
            link = link_info.get('link')

            if not protocol or not link:
                continue

            # Add to mixed output lists if enabled and protocol matches criteria
            # اضافه کردن به لیست‌های خروجی ترکیبی در صورت فعال بودن تنظیمات و تطابق پروتکل
            if settings.GENERATE_MIXED_PROTOCOL_FILE:
                if settings.PROTOCOLS_FOR_MIXED_OUTPUT: # If specific protocols are defined for mixed output
                    if protocol in settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                        mixed_links_plaintext.append(link)
                        mixed_links_base64.append(link) # For base64 mixed file
                else: # If no specific protocols are defined, include all active protocols in mixed output
                    if protocol in settings.ACTIVE_PROTOCOLS:
                        mixed_links_plaintext.append(link)
                        mixed_links_base64.append(link) # For base64 mixed file
            
            # Add to protocol-specific grouping if enabled
            # اضافه کردن به گروه‌بندی پروتکل-خاص در صورت فعال بودن تنظیمات
            if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
                if protocol in settings.ACTIVE_PROTOCOLS: # Only save for active protocols
                    protocol_specific_links_plaintext[protocol].append(link)
                    protocol_specific_links_base64[protocol].append(link) # For base64 protocol-specific files
        
        # Sort all relevant link lists alphabetically for consistency
        mixed_links_plaintext.sort()
        mixed_links_base64.sort()

        # Save mixed protocol files (if enabled)
        # ذخیره فایل‌های پروتکل ترکیبی (در صورت فعال بودن)
        if settings.GENERATE_MIXED_PROTOCOL_FILE:
            self._write_plaintext_file(settings.PLAINTEXT_MIXED_FILE, mixed_links_plaintext)
            self._write_base64_encoded_file(settings.BASE64_MIXED_FILE, mixed_links_base64)

        # Save protocol-specific files (if enabled)
        # ذخیره فایل‌های پروتکل-خاص (در صورت فعال بودن)
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            self._write_protocol_specific_files_pair(protocol_specific_links_plaintext, protocol_specific_links_base64)

        print("OutputManager: All configs saved to new respective files.")

    def _write_plaintext_file(self, file_path: str, links: List[str]):
        """Writes a list of links to a file, each on a new line (plaintext)."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                for link in links:
                    f.write(link + '\n')
            print(f"OutputManager: Saved {len(links)} plaintext links to {file_path}")
        except Exception as e:
            print(f"OutputManager: Error saving plaintext links to {file_path}: {e}")

    def _write_base64_encoded_file(self, file_path: str, links: List[str]):
        """
        Encodes a list of links to base64 and writes them to a file.
        Includes a header if enabled in settings.
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            concatenated_links = "\n".join(links)
            encoded_bytes = base64.b64encode(concatenated_links.encode('utf-8'))
            encoded_string = encoded_bytes.decode('utf-8')

            with open(file_path, 'w', encoding='utf-8') as f:
                if settings.OUTPUT_HEADER_BASE64_ENABLED:
                    header_template = """//profile-title: base64:{}
//profile-update-interval: 1
//subscription-userinfo: upload=0; download=0; total=10737418240000000; expire=2546249531
//support-url: https://t.me/your_support_channel # Replace with your actual support channel
//profile-web-page-url: https://github.com/your_repo # Replace with your actual repo
"""
                    default_title = "My-Config-Subscription"
                    encoded_title = base64.b64encode(default_title.encode('utf-8')).decode('utf-8')
                    f.write(header_template.format(encoded_title) + "\n")

                f.write(encoded_string)
            print(f"OutputManager: Saved {len(links)} base64 encoded links to {file_path}")
        except Exception as e:
            print(f"OutputManager: Error saving base64 encoded links to {file_path}: {e}")

    def _write_protocol_specific_files_pair(self, 
                                             plaintext_links_by_protocol: Dict[str, List[str]], 
                                             base64_links_by_protocol: Dict[str, List[str]]):
        """
        Writes separate files for each protocol in both plaintext/protocols/ and base64/protocols/.
        """
        print(f"OutputManager: Generating protocol-specific files in '{settings.FULL_PLAINTEXT_PROTOCOL_SPECIFIC_DIR}' and '{settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR}'...")
        
        # Plaintext protocol-specific files
        os.makedirs(settings.FULL_PLAINTEXT_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
        for protocol, links in plaintext_links_by_protocol.items():
            if not links: continue
            links.sort()
            file_name = f"{protocol}_links.txt"
            file_path = os.path.join(settings.FULL_PLAINTEXT_PROTOCOL_SPECIFIC_DIR, file_name)
            self._write_plaintext_file(file_path, links)
        
        # Base64 protocol-specific files
        os.makedirs(settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
        for protocol, links in base64_links_by_protocol.items():
            if not links: continue
            links.sort()
            file_name = f"{protocol}_links.txt"
            file_path = os.path.join(settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR, file_name)
            self._write_base64_encoded_file(file_path, links)

# Create a global instance of OutputManager
output_manager = OutputManager()
