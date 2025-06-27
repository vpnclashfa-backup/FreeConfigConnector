# src/utils/stats_reporter.py

from collections import defaultdict

class StatsReporter:
    def __init__(self):
        # آمار کلی کانفیگ‌های جمع‌آوری شده
        self.total_collected_links = 0
        self.unique_collected_links = 0

        # آمار بر اساس پروتکل
        self.links_by_protocol = defaultdict(int)

        # آمار بر اساس منبع (کانال تلگرام یا وب‌سایت)
        # { "source_type": { "source_name": { "total": X, "protocol_counts": {"ss": Y, "vmess": Z} } } }
        self.links_by_source = defaultdict(lambda: defaultdict(lambda: {"total": 0, "protocol_counts": defaultdict(int)}))

        # آمار کشفیات جدید
        self.discovered_telegram_channels_count = 0
        self.discovered_websites_count = 0

        # آمار منابع تایم‌آوت شده در این اجرا
        self.newly_timed_out_telegram_channels = []
        self.newly_timed_out_websites = []

    def increment_total_collected(self):
        self.total_collected_links += 1

    def set_unique_collected(self, count):
        self.unique_collected_links = count

    def increment_protocol_count(self, protocol):
        self.links_by_protocol[protocol] += 1

    def record_source_link(self, source_type, source_name, protocol):
        """
        Records a link collected from a specific source for detailed statistics.
        source_type: "telegram" or "web"
        source_name: e.g., "@channel_name" or "https://website.com"
        protocol: e.g., "ss", "vmess"
        """
        self.links_by_source[source_type][source_name]["total"] += 1
        self.links_by_source[source_type][source_name]["protocol_counts"][protocol] += 1

    def increment_discovered_channel_count(self):
        self.discovered_telegram_channels_count += 1

    def increment_discovered_website_count(self):
        self.discovered_websites_count += 1

    def add_newly_timed_out_channel(self, channel_username):
        if channel_username not in self.newly_timed_out_telegram_channels:
            self.newly_timed_out_telegram_channels.append(channel_username)

    def add_newly_timed_out_website(self, url):
        if url not in self.newly_timed_out_websites:
            self.newly_timed_out_websites.append(url)

    def generate_report(self):
        """Generates and prints a comprehensive collection report."""
        report = "\n" + "="*50
        report += "\nCollection Summary Report"
        report += "\n" + "="*50

        report += f"\nTotal Links Collected (Raw): {self.total_collected_links}"
        report += f"\nTotal Unique Links (After Deduplication): {self.unique_collected_links}"

        report += "\n\n--- Links by Protocol ---"
        if not self.links_by_protocol:
            report += "\nNo links collected by protocol."
        else:
            for protocol, count in sorted(self.links_by_protocol.items()):
                report += f"\n- {protocol}: {count}"

        report += "\n\n--- Links by Source ---"
        if not self.links_by_source:
            report += "\nNo links collected from sources."
        else:
            for source_type, sources in self.links_by_source.items():
                report += f"\n{source_type.upper()} Sources:"
                for source_name, data in sources.items():
                    report += f"\n  - {source_name}: Total {data['total']} links"
                    for protocol, count in sorted(data['protocol_counts'].items()):
                        report += f"\n    -> {protocol}: {count}"

        report += "\n\n--- Discovery Summary ---"
        report += f"\nNew Telegram Channels Discovered: {self.discovered_telegram_channels_count}"
        report += f"\nNew Websites Discovered: {self.discovered_websites_count}"

        report += "\n\n--- Source Management Summary ---"
        if self.newly_timed_out_telegram_channels:
            report += "\nNewly Timed Out Telegram Channels (due to repeated errors):"
            for channel in self.newly_timed_out_telegram_channels:
                report += f"\n- {channel}"
        else:
            report += "\nNo Telegram channels newly timed out in this run."

        if self.newly_timed_out_websites:
            report += "\nNewly Timed Out Websites (due to repeated errors):"
            for website in self.newly_timed_out_websites:
                report += f"\n- {website}"
        else:
            report += "\nNo websites newly timed out in this run."

        report += "\n" + "="*50
        print(report)

# یک نمونه سراسری از StatsReporter
stats_reporter = StatsReporter()
