# src/utils/stats_reporter.py

from datetime import datetime, timedelta

class StatsReporter:
    def __init__(self):
        self.reset_stats()

    def reset_stats(self):
        """Resets all statistics."""
        self.start_time = None
        self.end_time = None
        self.total_collected_links = 0
        self.protocol_counts = {} # e.g., {'vmess': 10, 'ss': 5}
        self.source_link_counts = {} # e.g., {'telegram': {'@channel1': {'vmess': 2, 'ss': 1}}, 'web': {'https://site.com': {'trojan': 3}}}
        self.discovered_channel_count = 0
        self.discovered_website_count = 0
        self.initial_active_telegram_channels = 0
        self.initial_active_websites = 0
        self.newly_timed_out_channels = set()
        self.newly_timed_out_websites = set()

    def start_report(self, initial_active_telegram_channels, initial_active_websites):
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

    def increment_total_collected(self):
        """Increments the total count of collected links."""
        self.total_collected_links += 1

    def increment_protocol_count(self, protocol):
        """Increments the count for a specific protocol."""
        self.protocol_counts[protocol] = self.protocol_counts.get(protocol, 0) + 1

    def record_source_link(self, source_type, source_name, protocol):
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

    def add_newly_timed_out_channel(self, channel_name):
        """Adds a Telegram channel that newly entered timeout state."""
        self.newly_timed_out_channels.add(channel_name)

    def add_newly_timed_out_website(self, website_url):
        """Adds a website that newly entered timeout state."""
        self.newly_timed_out_websites.add(website_url)

    def generate_report(self, source_manager_instance):
        """Generates a comprehensive report of the collection process."""
        report_lines = ["\n--- Collection Report ---"]

        # General Stats
        report_lines.append(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'N/A'}")
        report_lines.append(f"End Time: {self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else 'N/A'}")
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            report_lines.append(f"Duration: {str(duration).split('.')[0]}") # Remove microseconds

        report_lines.append(f"\nTotal Links Collected: {self.total_collected_links}")

        # Protocol Breakdown
        report_lines.append("\nLinks by Protocol:")
        if self.protocol_counts:
            for protocol, count in sorted(self.protocol_counts.items(), key=lambda item: item[1], reverse=True):
                report_lines.append(f"  - {protocol}: {count}")
        else:
            report_lines.append("  No links collected by protocol.")

        # Source Management Stats
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

        # Detailed Source Status with Scores
        report_lines.append("\n--- Current Source Status (Active & Timed Out) ---")

        # Telegram Channels
        report_lines.append("\nTelegram Channels:")
        active_telegram_channels_with_scores = [
            (ch, source_manager_instance._all_telegram_scores.get(ch, 0))
            for ch in source_manager_instance.get_active_telegram_channels() # get_active_telegram_channels already sorts by score
        ]
        if active_telegram_channels_with_scores:
            report_lines.append("  Active (Sorted by Score - Highest First):")
            for ch, score in active_telegram_channels_with_scores:
                report_lines.append(f"    - {ch} (Score: {score})")
        else:
            report_lines.append("  No active Telegram channels.")

        timed_out_telegram_channels_with_scores = [
            (ch, data.get("score", 0), datetime.fromisoformat(data.get("last_timeout", datetime.now().isoformat())))
            for ch, data in source_manager_instance.timeout_telegram_channels.items()
        ]
        # Sort timed out channels by score (lowest first)
        timed_out_telegram_channels_with_scores.sort(key=lambda x: x[1]) 

        if timed_out_telegram_channels_with_scores:
            report_lines.append("  Timed Out (Sorted by Score - Lowest First):")
            for ch, score, last_timeout_dt in timed_out_telegram_channels_with_scores:
                time_since_timeout = datetime.now(last_timeout_dt.tzinfo) - last_timeout_dt
                recovery_status = ""
                if time_since_timeout >= settings.TIMEOUT_RECOVERY_DURATION:
                    recovery_status = " (Ready for recovery)"
                else:
                    remaining_time = settings.TIMEOUT_RECOVERY_DURATION - time_since_timeout
                    # Format remaining_time to show days, hours, minutes
                    days = remaining_time.days
                    seconds = remaining_time.seconds
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    recovery_status = f" (Recovers in {days}d {hours}h {minutes}m)"
                report_lines.append(f"    - {ch} (Score: {score}, Last Timeout: {last_timeout_dt.strftime('%Y-%m-%d %H:%M:%S')}{recovery_status})")
        else:
            report_lines.append("  No timed out Telegram channels.")


        # Websites
        report_lines.append("\nWebsites:")
        active_websites_with_scores = [
            (ws, source_manager_instance._all_website_scores.get(ws, 0))
            for ws in source_manager_instance.get_active_websites() # get_active_websites already sorts by score
        ]
        if active_websites_with_scores:
            report_lines.append("  Active (Sorted by Score - Highest First):")
            for ws, score in active_websites_with_scores:
                report_lines.append(f"    - {ws} (Score: {score})")
        else:
            report_lines.append("  No active websites.")

        timed_out_websites_with_scores = [
            (ws, data.get("score", 0), datetime.fromisoformat(data.get("last_timeout", datetime.now().isoformat())))
            for ws, data in source_manager_instance.timeout_websites.items()
        ]
        # Sort timed out websites by score (lowest first)
        timed_out_websites_with_scores.sort(key=lambda x: x[1])

        if timed_out_websites_with_scores:
            report_lines.append("  Timed Out (Sorted by Score - Lowest First):")
            for ws, score, last_timeout_dt in timed_out_websites_with_scores:
                time_since_timeout = datetime.now(last_timeout_dt.tzinfo) - last_timeout_dt
                recovery_status = ""
                if time_since_timeout >= settings.TIMEOUT_RECOVERY_DURATION:
                    recovery_status = " (Ready for recovery)"
                else:
                    remaining_time = settings.TIMEOUT_RECOVERY_DURATION - time_since_timeout
                    days = remaining_time.days
                    seconds = remaining_time.seconds
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    recovery_status = f" (Recovers in {days}d {hours}h {minutes}m)"
                report_lines.append(f"    - {ws} (Score: {score}, Last Timeout: {last_timeout_dt.strftime('%Y-%m-%d %H:%M:%S')}{recovery_status})")
        else:
            report_lines.append("  No timed out websites.")


        # Links by Source Breakdown
        report_lines.append("\n--- Links Collected by Source ---")
        if self.source_link_counts:
            for source_type, sources in self.source_link_counts.items():
                report_lines.append(f"\n{source_type.capitalize()} Sources:")
                # Sort sources by total links collected from them (descending)
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
