# src/utils/output_manager.py

import os
import base64
from typing import List, Dict
from collections import defaultdict # New: To group links by protocol
from src.utils.settings_manager import settings

class OutputManager:
    def __init__(self):
        # Ensure output and subs directories exist
        # اطمینان از وجود پوشه‌های خروجی اصلی
        os.makedirs(settings.FULL_SUB_DIR_PATH, exist_ok=True)
        # Create sub-directories for base64 and plaintext based on their file paths
        # ایجاد زیرپوشه‌های مخصوص برای هر نوع خروجی (base64, plaintext, mixed)
        os.makedirs(os.path.dirname(settings.BASE64_SUB_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(settings.PLAINTEXT_SUB_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(settings.MIXED_PROTOCOLS_SUB_FILE), exist_ok=True)
        
        # New: Create directory for protocol-specific files if enabled
        # جدید: ایجاد پوشه برای فایل‌های پروتکل-خاص در صورت فعال بودن تنظیمات
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            os.makedirs(settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH, exist_ok=True)
            print(f"OutputManager: Protocol-specific directory '{settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH}' ensured.")
        
        print("OutputManager: Core output directories ensured.")


    def save_configs(self, unique_links: List[Dict]):
        """
        Saves collected unique links into structured output files (Base64, Plaintext, Mixed, and Protocol-specific).
        لینک‌های منحصر به فرد جمع‌آوری شده را در فایل‌های خروجی ساختاریافته (بیس۶۴، متن ساده، ترکیبی و پروتکل-خاص) ذخیره می‌کند.
        """
        print("\nOutputManager: Saving collected configs...")
        
        plaintext_links = []
        base64_links_to_encode = [] # Links that will be base64 encoded for the file
        mixed_output_links = [] # Links for the mixed file
        protocol_specific_links = defaultdict(list) # NEW: To group links by protocol for separate files
        

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
            if settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                if protocol in settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                    mixed_output_links.append(link)
            else: # If no specific protocols are defined for mixed, include all active protocols
                if protocol in settings.ACTIVE_PROTOCOLS:
                    mixed_output_links.append(link)
            
            # NEW: Add to protocol-specific grouping
            if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
                if protocol in settings.ACTIVE_PROTOCOLS: # Only save for active protocols
                    protocol_specific_links[protocol].append(link)
        
        # Sort links alphabetically for consistency
        plaintext_links.sort()
        base64_links_to_encode.sort()
        mixed_output_links.sort()
        # No need to sort protocol_specific_links here, they are sorted before writing to file

        # Save Plaintext File
        self._write_plaintext_file(settings.PLAINTEXT_SUB_FILE, plaintext_links)

        # Save Base64 File
        self._write_base64_file(settings.BASE64_SUB_FILE, base64_links_to_encode)

        # Save Mixed Protocols File
        self._write_plaintext_file(settings.MIXED_PROTOCOLS_SUB_FILE, mixed_output_links)

        # NEW: Save Protocol-Specific Files
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            self._write_protocol_specific_files(protocol_specific_links)

        print("OutputManager: All configs saved to respective files.")

    def _write_plaintext_file(self, file_path: str, links: List[str]):
        """Writes a list of links to a file, each on a new line."""
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
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
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
            print(f"OutputManager: Error saving base64 links to {file_path}: {e}")

    def _write_protocol_specific_files(self, protocol_links: Dict[str, List[str]]):
        """
        Writes separate files for each protocol in the protocol_specific_dir.
        فایل‌های جداگانه برای هر پروتکل را در پوشه protocol_specific_dir می‌نویسد.
        """
        print(f"OutputManager: Generating protocol-specific files in '{settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH}'...")
        os.makedirs(settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH, exist_ok=True)

        for protocol, links in protocol_links.items():
            if not links:
                continue # Skip if no links for this protocol
            
            # Sort links for consistency in each file
            links.sort()

            file_name = f"{protocol}_links.txt" # e.g., vmess_links.txt
            file_path = os.path.join(settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH, file_name)
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for link in links:
                        f.write(link + '\n')
                print(f"OutputManager: Saved {len(links)} {protocol} links to {file_path}")
            except Exception as e:
                print(f"OutputManager: Error saving {protocol} links to {file_path}: {e}")

# Create a global instance of OutputManager
output_manager = OutputManager()
