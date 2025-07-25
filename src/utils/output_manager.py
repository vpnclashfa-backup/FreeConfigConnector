import os
import base64
from typing import List, Dict
from collections import defaultdict
from src.utils.settings_manager import settings

class OutputManager:
    def __init__(self):
        # Ensure base output and subs directories exist
        os.makedirs(settings.FULL_SUB_DIR_PATH, exist_ok=True)
        print(f"OutputManager: Ensured base subscription directory: {settings.FULL_SUB_DIR_PATH}")

        # Ensure plaintext and base64 main directories exist
        os.makedirs(settings.FULL_PLAINTEXT_OUTPUT_PATH, exist_ok=True)
        os.makedirs(settings.FULL_BASE64_OUTPUT_PATH, exist_ok=True)
        print(f"OutputManager: Ensured plaintext output path: {settings.FULL_PLAINTEXT_OUTPUT_PATH}")
        print(f"OutputManager: Ensured base64 output path: {settings.FULL_BASE64_OUTPUT_PATH}")

        # Create protocol-specific sub-directories within both plaintext and base64
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            os.makedirs(settings.FULL_PLAINTEXT_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
            os.makedirs(settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
            print(f"OutputManager: Protocol-specific directories ensured under plaintext/protocols and base64/protocols.")

        print("OutputManager: Core output directories for new structure ensured.")


    def save_configs(self, unique_links: List[Dict]):
        """
        Saves collected unique links into the new structured output files.
        لینک‌های منحصر به فرد جمع‌آوری شده را در فایل‌های خروجی ساختاریافته جدید ذخیره می‌کند.
        """
        print(f"\nOutputManager: Saving {len(unique_links)} unique collected configs to new structure...")

        mixed_links_plaintext: List[str] = [] 
        mixed_links_base64: List[str] = []

        protocol_specific_links_plaintext: Dict[str, List[str]] = defaultdict(list)
        protocol_specific_links_base64: Dict[str, List[str]] = defaultdict(list)

        for link_info in unique_links:
            protocol = link_info.get('protocol')
            link = link_info.get('link')

            if not protocol or not link:
                print(f"OutputManager: WARNING: Received incomplete link_info: {link_info}. Skipping.")
                continue

            # Add to mixed output lists if enabled and protocol matches criteria
            if settings.GENERATE_MIXED_PROTOCOL_FILE:
                if settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                    if protocol in settings.PROTOCOLS_FOR_MIXED_OUTPUT:
                        mixed_links_plaintext.append(link)
                        mixed_links_base64.append(link)
                elif protocol in settings.ACTIVE_PROTOCOLS: # If no specific protocols are defined, include all active protocols in mixed output
                    mixed_links_plaintext.append(link)
                    mixed_links_base64.append(link)

            # Add to protocol-specific grouping if enabled
            if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
                if protocol in settings.ACTIVE_PROTOCOLS: # Only save for active protocols
                    protocol_specific_links_plaintext[protocol].append(link)
                    protocol_specific_links_base64[protocol].append(link)

        # Sort all relevant link lists alphabetically for consistency
        mixed_links_plaintext.sort()
        mixed_links_base64.sort()

        # Save mixed protocol files (if enabled)
        if settings.GENERATE_MIXED_PROTOCOL_FILE:
            print(f"OutputManager: Attempting to save {len(mixed_links_plaintext)} mixed plaintext links to {settings.PLAINTEXT_MIXED_FILE}")
            self._write_plaintext_file(settings.PLAINTEXT_MIXED_FILE, mixed_links_plaintext)
            print(f"OutputManager: Attempting to save {len(mixed_links_base64)} mixed base64 links to {settings.BASE64_MIXED_FILE}")
            self._write_base64_encoded_file(settings.BASE64_MIXED_FILE, mixed_links_base64)
        else:
            print("OutputManager: Mixed protocol file generation is disabled in settings.")

        # Save protocol-specific files (if enabled)
        if settings.GENERATE_PROTOCOL_SPECIFIC_FILES:
            self._write_protocol_specific_files_pair(protocol_specific_links_plaintext, protocol_specific_links_base64)
        else:
            print("OutputManager: Protocol-specific file generation is disabled in settings.")

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
            print(f"OutputManager: ERROR saving plaintext links to {file_path}: {e}")
            # traceback.print_exc() # Uncomment for full traceback if needed

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
                    print(f"OutputManager: Added Base64 header to {file_path}.")
                else:
                    print(f"OutputManager: Base64 header is disabled for {file_path}.")

                f.write(encoded_string)
            print(f"OutputManager: Saved {len(links)} base64 encoded links to {file_path}")
        except Exception as e:
            print(f"OutputManager: ERROR saving base64 encoded links to {file_path}: {e}")
            # traceback.print_exc() # Uncomment for full traceback if needed


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
            if not links:
                print(f"OutputManager: No plaintext links for protocol '{protocol}'. Skipping file creation for plaintext.")
                continue
            links.sort()
            file_name = f"{protocol}_links.txt"
            file_path = os.path.join(settings.FULL_PLAINTEXT_PROTOCOL_SPECIFIC_DIR, file_name)
            self._write_plaintext_file(file_path, links)

        # Base64 protocol-specific files
        os.makedirs(settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR, exist_ok=True)
        for protocol, links in base64_links_by_protocol.items():
            if not links:
                print(f"OutputManager: No base64 links for protocol '{protocol}'. Skipping file creation for base64.")
                continue
            links.sort()
            file_name = f"{protocol}_links.txt"
            file_path = os.path.join(settings.FULL_BASE64_PROTOCOL_SPECIFIC_DIR, file_name)
            self._write_base64_encoded_file(file_path, links)

# Create a global instance of OutputManager
output_manager = OutputManager()