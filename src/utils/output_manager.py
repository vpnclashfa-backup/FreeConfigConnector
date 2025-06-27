# src/utils/output_manager.py

import os
import base64
from typing import List, Dict # CORRECT: List and Dict are imported
from collections import defaultdict 
from src.utils.settings_manager import settings

class OutputManager:
    def __init__(self):
        os.makedirs(settings.FULL_SUB_DIR_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(settings.BASE64_SUB_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(settings.PLAINTEXT_SUB_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(settings.MIXED_PROTOCOLS_SUB_FILE), exist_ok=True)
        
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            os.makedirs(settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH, exist_ok=True)
            print(f"OutputManager: Protocol-specific directory '{settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH}' ensured.")
        
        print("OutputManager: Core output directories ensured.")

    def save_configs(self, unique_links: List[Dict]):
        """
        Saves collected unique links into structured output files (Base64, Plaintext, Mixed, and Protocol-specific).
        """
        print("\nOutputManager: Saving collected configs...")
        
        plaintext_links: List[str] = []
        base64_links_to_encode: List[str] = []
        mixed_output_links: List[str] = []
        protocol_specific_links: Dict[str, List[str]] = defaultdict(list)
        

        for link_info in unique_links:
            protocol = link_info.get('protocol')
            link = link_info.get('link')

            if not protocol or not link:
                continue

            plaintext_links.append(link)
            base64_links_to_encode.append(link)

            if settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                if protocol in settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                    mixed_output_links.append(link)
            else:
                if protocol in settings.ACTIVE_PROTOCOLS:
                    mixed_output_links.append(link)
            
            if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
                if protocol in settings.ACTIVE_PROTOCOLS:
                    protocol_specific_links[protocol].append(link)
        
        plaintext_links.sort()
        base64_links_to_encode.sort()
        mixed_output_links.sort()

        self._write_plaintext_file(settings.PLAINTEXT_SUB_FILE, plaintext_links)
        self._write_base64_file(settings.BASE64_SUB_FILE, base64_links_to_encode)
        self._write_plaintext_file(settings.MIXED_PROTOCOLS_SUB_FILE, mixed_output_links)

        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            self._write_protocol_specific_files(protocol_specific_links)

        print("OutputManager: All configs saved to respective files.")

    def _write_plaintext_file(self, file_path: str, links: List[str]):
        """Writes a list of links to a file, each on a new line."""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
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
            print(f"OutputManager: Error saving base64 links to {file_path}: {e}")

    def _write_protocol_specific_files(self, protocol_links: Dict[str, List[str]]):
        """
        Writes separate files for each protocol in the protocol_specific_dir.
        """
        print(f"OutputManager: Generating protocol-specific files in '{settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH}'...")
        os.makedirs(settings.FULL_PROTOCOL_SPECIFIC_DIR_PATH, exist_ok=True)

        for protocol, links in protocol_links.items():
            if not links:
                continue
            
            links.sort()

            file_name = f"{protocol}_links.txt"
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
