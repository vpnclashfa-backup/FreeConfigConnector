# src/utils/stats_reporter.py

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Set, Optional # Import Optional

class StatsReporter:
    def __init__(self):
        self.reset_stats()

    def reset_stats(self):
        """Resets all statistics."""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_collected_links: int = 0
        self.unique_collected_links: int = 0 # NEW: Add this attribute
        self.protocol_counts: Dict[str, int] = {}
        self.source_link_counts: Dict[str, Dict[str, Dict[str, int]]] = {} # type: ignore
        self.discovered_channel_count: int = 0
        self.discovered_website_count: int = 0
        self.initial_active_telegram_channels: int = 0
        self.initial_active_websites: int = 0
        self.newly_timed_out_channels: Set[str] = set()
        self.newly_timed_out_websites: Set[str] = set()

    def start_report(self, initial_active_telegram_channels: int, initial_active_websites: int):
        """Starts the reporting period."""
        self.reset_stats()
        self.start_time = datetime.now()
        self.initial_active_telegram_channels = initial_active_telegram_channels
        self.initial_active_websites = initial_active_websites
        print("StatsReporter: Reporting started.")

    def end_report(self):
        """Ends the reporting period."""
        self.end_time = datetime.now()
        print("StatsReporter: Reporting ended.")

    def set_unique_collected(self, count: int): # NEW: Add this method
        """Sets the total count of unique collected links."""
        self.unique_collected_links = count

    def increment_total_collected(self):
        """Increments the total count of collected links."""
        self.total_collected_links += 1

    def increment_protocol_count(self, protocol: str):
        """Increments the count for a specific protocol."""
        self.protocol_counts[protocol] = self.protocol_counts.get(protocol, 0) + 1

    def record_source_link(self, source_type: str, source_name: str, protocol: str):
        """Records a link found from a specific source."""
        if source_type not in self.source_link_counts:
            self.source_link_counts[source_type] = {}
        if source_name not in self.source_link_counts[source_type]:
            self.source_link_counts[source_type][source_name] = {}
        
        self.source_link_counts[source_type][source_name][protocol] = \
            self.source_link_counts[source_type][source_name].get(protocol, 0) + 1

    def increment_discovered_channel_count(self):
        """Increments the count of newly discovered Telegram channels."""
        self.discovered_channel_count += 1

    def increment_discovered_website_count(self):
        """Increments the count of newly discovered websites."""
        self.discovered_website_count += 1

    def add_newly_timed_out_channel(self, channel_name: str):
        """Adds a Telegram channel that newly entered timeout state."""
        self.newly_timed_out_channels.add(channel_name)

    def add_newly_timed_out_website(self, website_url: str):
        """Adds a website that newly entered timeout state."""
        self.newly_timed_out_websites.add(website_url)

    def generate_report(self, source_manager_instance): # source_manager_instance is passed from main
        """Generates a comprehensive report of the collection process."""
        report_lines: List[str] = ["\n--- Collection Report ---"]

        report_lines.append(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'}")
        report_lines.append(f"End Time: {self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else 'N/A'}")
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            report_lines.append(f"Duration: {str(duration).split('.')[0]}")

        report_lines.append(f"\nTotal Links Collected (Raw): {self.total_collected_links}")
        report_lines.append(f"Total Unique Links (After Deduplication): {self.unique_collected_links}") # NEW: Use unique_collected_links

        report_lines.append("\nLinks by Protocol:")
        if self.protocol_counts:
            for protocol, count in sorted(self.protocol_counts.items(), key=lambda item: item[1], reverse=True):
                report_lines.append(f"  - {protocol}: {count}")
        else:
            report_lines.append("  No links collected by protocol.")

        report_lines.append("\n--- Source Management Stats ---")
        report_lines.append(f"Initial Active Telegram Channels: {self.initial_active_telegram_channels}")
        report_lines.append(f"Initial Active Websites: {self.initial_active_websites}")
        report_lines.append(f"Newly Discovered Telegram Channels: {self.discovered_channel_count}")
        report_lines.append(f"Newly Discovered Websites: {self.discovered_website_count}")
        report_lines.append(f"Channels Newly Timed Out in this Run: {len(self.newly_timed_out_channels)}")
        for ch in self.newly_timed_out_channels:
            report_lines.append(f"  - {ch}")
        report_lines.append(f"Websites Newly Timed Out in this Run: {len(self.newly_timed_out_websites)}")
        for ws in self.newly_timed_out_websites:
            report_lines.append(f"  - {ws}")

        report_lines.append("\n--- Current Source Status (Active & Timed Out) ---")
        
        report_lines.append("\nTelegram Channels:")
        # get_active_telegram_channels already sorts by score
        active_telegram_channels_with_scores: List[tuple[str, int]] = [ 
            (ch, source_manager_instance._all_telegram_scores.get(ch, 0))
            for ch in source_manager_instance.get_active_telegram_channels() 
        ]
        if active_telegram_channels_with_scores:
            report_lines.append("  Active (Sorted by Score - Highest First):")
            for ch, score in active_telegram_channels_with_scores:
                report_lines.append(f"    - {ch} (Score: {score})")
        else:
            report_lines.append("  No active Telegram channels.")

        timed_out_telegram_channels_with_scores: List[Dict] = source_manager_instance.get_timed_out_telegram_channels()
        
        if timed_out_telegram_channels_with_scores:
            report_lines.append("  Timed Out (Sorted by Score - Lowest First):")
            for item in timed_out_telegram_channels_with_scores:
                ch = item['channel']
                score = item['score']
                last_timeout_str = item.get("last_timeout")
                last_timeout_dt: Optional[datetime] = datetime.fromisoformat(last_timeout_str) if last_timeout_str else None

                recovery_status = ""
                if last_timeout_dt:
                    # Need to import settings into stats_reporter to get TIMEOUT_RECOVERY_DURATION
                    from src.utils.settings_manager import settings as report_settings # Temporarily import settings for calculation
                    time_since_timeout = datetime.now(last_timeout_dt.tzinfo if last_timeout_dt.tzinfo else timezone.utc) - last_timeout_dt
                    if time_since_timeout >= report_settings.TIMEOUT_RECOVERY_DURATION: # Use report_settings here
                        recovery_status = " (Ready for recovery)"
                    else:
                        remaining_time = report_settings.TIMEOUT_RECOVERY_DURATION - time_since_timeout # Use report_settings
                        days = remaining_time.days
                        seconds = remaining_time.seconds
                        hours = seconds // 3600
                        minutes = (seconds % 3600) // 60
                        recovery_status = f" (Recovers in {days}d {hours}h {minutes}m)"
                    report_lines.append(f"    - {ch} (Score: {score}, Last Timeout: {last_timeout_dt.strftime('%Y-%m-%d %H:%M:%S')}{recovery_status})")
                else:
                     report_lines.append(f"    - {ch} (Score: {score}, Last Timeout: N/A)")
        else:
            report_lines.append("  No timed out Telegram channels.")


        report_lines.append("\nWebsites:")
        active_websites_with_scores: List[tuple[str, int]] = [
            (ws, source_manager_instance._all_website_scores.get(ws, 0))
            for ws in source_manager_instance.get_active_websites()
        ]
        if active_websites_with_scores:
            report_lines.append("  Active (Sorted by Score - Highest First):")
            for ws, score in active_websites_with_scores:
                report_lines.append(f"    - {ws} (Score: {score})")
        else:
            report_lines.append("  No active websites.")

        timed_out_websites_with_scores: List[Dict] = source_manager_instance.get_timed_out_websites()

        if timed_out_websites_with_scores:
            report_lines.append("  Timed Out (Sorted by Score - Lowest First):")
            for item in timed_out_websites_with_scores:
                ws = item['website']
                score = item['score']
                last_timeout_str = item.get("last_timeout")
                last_timeout_dt: Optional[datetime] = datetime.fromisoformat(last_timeout_str) if last_timeout_str else None

                recovery_status = ""
                if last_timeout_dt:
                    from src.utils.settings_manager import settings as report_settings # Temporarily import settings for calculation
                    time_since_timeout = datetime.now(last_timeout_dt.tzinfo if last_timeout_dt.tzinfo else timezone.utc) - last_timeout_dt
                    if time_since_timeout >= report_settings.TIMEOUT_RECOVERY_DURATION:
                        recovery_status = " (Ready for recovery)"
                    else:
                        remaining_time = report_settings.TIMEOUT_RECOVERY_DURATION - time_since_timeout
                        days = remaining_time.days
                        seconds = remaining_time.seconds
                        hours = seconds // 3600
                        minutes = (seconds % 3600) // 60
                        recovery_status = f" (Recovers in {days}d {hours}h {minutes}m)"
                    report_lines.append(f"    - {ws} (Score: {score}, Last Timeout: {last_timeout_dt.strftime('%Y-%m-%d %H:%M:%S')}{recovery_status})")
                else:
                    report_lines.append(f"    - {ws} (Score: {score}, Last Timeout: N/A)")
        else:
            report_lines.append("  No timed out websites.")


        report_lines.append("\n--- Links Collected by Source ---")
        if self.source_link_counts:
            for source_type, sources in self.source_link_counts.items():
                report_lines.append(f"\n{source_type.capitalize()} Sources:")
                sorted_sources = sorted(sources.items(), key=lambda item: sum(item[1].values()), reverse=True)
                for source_name, protocols in sorted_sources:
                    total_links_from_source = sum(protocols.values())
                    report_lines.append(f"  - {source_name} (Total: {total_links_from_source})")
                    for protocol, count in sorted(protocols.items(), key=lambda item: item[1], reverse=True):
                        report_lines.append(f"    - {protocol}: {count}")
        else:
            report_lines.append("  No links collected from any source.")

        report_lines.append("\n--- Report End ---")
        return "\n".join(report_lines)

stats_reporter = StatsReporter()
