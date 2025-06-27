# src/utils/stats_reporter.py

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Set, Optional

# import settings inside generate_report where needed to avoid circular dependency on init
# from src.utils.settings_manager import settings as current_settings

class StatsReporter:
    def __init__(self):
        self.reset_stats()

    def reset_stats(self):
        """Resets all statistics."""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_collected_links: int = 0
        self.unique_collected_links: int = 0
        self.protocol_counts: Dict[str, int] = {}
        self.source_link_counts: Dict[str, Dict[str, Dict[str, int]]] = {} # {source_type: {source_name: {protocol: count}}}
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

    def set_unique_collected(self, count: int):
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

    def generate_report(self, source_manager_instance) -> str:
        """
        Generates a comprehensive report of the collection process in Farsi Markdown format.
        گزارش جامعی از فرآیند جمع‌آوری را در قالب Markdown فارسی تولید می‌کند.
        """
        # Import settings here to avoid circular dependency
        from src.utils.settings_manager import settings as current_settings

        report_lines: List[str] = []

        report_lines.append("# گزارش جامع جمع‌آوری کانفیگ‌ها")
        report_lines.append(f"آخرین به‌روزرسانی: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
        report_lines.append("---")

        # زمان‌بندی کلی
        report_lines.append("## ۱. خلاصه‌ی زمان‌بندی")
        report_lines.append(f"- زمان شروع: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'نامشخص'}")
        report_lines.append(f"- زمان پایان: {self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else 'نامشخص'}")
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            report_lines.append(f"- مدت زمان اجرا: {str(duration).split('.')[0]}")
        report_lines.append("\n")

        # خلاصه‌ی لینک‌ها
        report_lines.append("## ۲. خلاصه‌ی لینک‌ها")
        report_lines.append(f"- مجموع لینک‌های جمع‌آوری شده (خام): **{self.total_collected_links}**")
        report_lines.append(f"- مجموع لینک‌های منحصر به فرد (پس از حذف تکراری‌ها): **{self.unique_collected_links}**")
        report_lines.append("\n")

        # تفکیک بر اساس پروتکل
        report_lines.append("### ۲.۱. تفکیک لینک‌ها بر اساس پروتکل")
        if self.protocol_counts:
            report_lines.append("| پروتکل | تعداد لینک |")
            report_lines.append("| :------ | :--------- |")
            for protocol, count in sorted(self.protocol_counts.items(), key=lambda item: item[1], reverse=True):
                report_lines.append(f"| {protocol} | {count} |")
        else:
            report_lines.append("هیچ لینکی بر اساس پروتکل جمع‌آوری نشده است.")
        report_lines.append("\n")

        # آمار مدیریت منابع
        report_lines.append("## ۳. آمار مدیریت منابع")
        report_lines.append(f"- کانال‌های فعال تلگرام (ابتدای اجرا): {self.initial_active_telegram_channels}")
        report_lines.append(f"- وب‌سایت‌های فعال (ابتدای اجرا): {self.initial_active_websites}")
        report_lines.append(f"- کانال‌های تلگرام تازه کشف شده: **{self.discovered_channel_count}**")
        report_lines.append(f"- وب‌سایت‌های تازه کشف شده: **{self.discovered_website_count}**")
        
        if self.newly_timed_out_channels:
            report_lines.append("\n### ۳.۱. کانال‌های تلگرام تازه تایم‌اوت شده (به دلیل خطاهای مکرر):")
            for ch in sorted(list(self.newly_timed_out_channels)):
                report_lines.append(f"- {ch}")
        else:
            report_lines.append("\nهیچ کانال تلگرامی جدیدی در این اجرا تایم‌اوت نشده است.")

        if self.newly_timed_out_websites:
            report_lines.append("\n### ۳.۲. وب‌سایت‌های تازه تایم‌اوت شده (به دلیل خطاهای مکرر):")
            for ws in sorted(list(self.newly_timed_out_websites)):
                report_lines.append(f"- {ws}")
        else:
            report_lines.append("\nهیچ وب‌سایتی جدیدی در این اجرا تایم‌اوت نشده است.")
        report_lines.append("\n")

        # وضعیت فعلی منابع (فعال و تایم‌اوت شده)
        report_lines.append("## ۴. وضعیت فعلی منابع (فعال و تایم‌اوت شده)")
        
        # کانال‌های تلگرام
        report_lines.append("\n### ۴.۱. کانال‌های تلگرام:")
        active_telegram_channels_with_scores: List[tuple[str, int]] = [
            (ch, source_manager_instance._all_telegram_scores.get(ch, 0))
            for ch in source_manager_instance.get_active_telegram_channels() # این متد خودش مرتب شده بر اساس امتیاز
        ]
        if active_telegram_channels_with_scores:
            report_lines.append("\n**فعال (مرتب شده بر اساس امتیاز - بالاترین امتیاز اول):**")
            report_lines.append("| کانال | امتیاز |")
            report_lines.append("| :------ | :----- |")
            for ch, score in active_telegram_channels_with_scores:
                report_lines.append(f"| {ch} | {score} |")
        else:
            report_lines.append("هیچ کانال تلگرام فعالی در حال حاضر وجود ندارد.")

        timed_out_telegram_channels_with_scores: List[Dict] = source_manager_instance.get_timed_out_telegram_channels()
        if timed_out_telegram_channels_with_scores:
            report_lines.append("\n**تایم‌اوت شده (مرتب شده بر اساس امتیاز - پایین‌ترین امتیاز اول):**")
            report_lines.append("| کانال | امتیاز | آخرین تایم‌اوت | وضعیت بازیابی |")
            report_lines.append("| :------ | :----- | :------------ | :------------ |")
            for item in timed_out_telegram_channels_with_scores:
                ch = item['channel']
                score = item['score']
                last_timeout_str = item.get("last_timeout")
                last_timeout_dt: Optional[datetime] = datetime.fromisoformat(last_timeout_str) if last_timeout_str else None

                recovery_status = ""
                if last_timeout_dt:
                    time_since_timeout = datetime.now(last_timeout_dt.tzinfo if last_timeout_dt.tzinfo else timezone.utc) - last_timeout_dt
                    if time_since_timeout >= current_settings.TIMEOUT_RECOVERY_DURATION: # از current_settings استفاده شود
                        recovery_status = "آماده بازیابی"
                    else:
                        remaining_time = current_settings.TIMEOUT_RECOVERY_DURATION - time_since_timeout # از current_settings استفاده شود
                        days = remaining_time.days
                        seconds = remaining_time.seconds
                        hours = seconds // 3600
                        minutes = (seconds % 3600) // 60
                        recovery_status = f"{days} روز {hours} ساعت {minutes} دقیقه"
                    report_lines.append(f"| {ch} | {score} | {last_timeout_dt.strftime('%Y-%m-%d %H:%M:%S')} | {recovery_status} |")
                else:
                    report_lines.append(f"| {ch} | {score} | نامشخص | نامشخص |")
        else:
            report_lines.append("هیچ کانال تلگرامی در حال حاضر تایم‌اوت نشده است.")
        report_lines.append("\n")

        # وب‌سایت‌ها
        report_lines.append("### ۴.۲. وب‌سایت‌ها:")
        active_websites_with_scores: List[tuple[str, int]] = [
            (ws, source_manager_instance._all_website_scores.get(ws, 0))
            for ws in source_manager_instance.get_active_websites() # این متد خودش مرتب شده
        ]
        if active_websites_with_scores:
            report_lines.append("\n**فعال (مرتب شده بر اساس امتیاز - بالاترین امتیاز اول):**")
            report_lines.append("| وب‌سایت | امتیاز |")
            report_lines.append("| :------- | :----- |")
            for ws, score in active_websites_with_scores:
                report_lines.append(f"| {ws} | {score} |")
        else:
            report_lines.append("هیچ وب‌سایت فعالی در حال حاضر وجود ندارد.")

        timed_out_websites_with_scores: List[Dict] = source_manager_instance.get_timed_out_websites()
        if timed_out_websites_with_scores:
            report_lines.append("\n**تایم‌اوت شده (مرتب شده بر اساس امتیاز - پایین‌ترین امتیاز اول):**")
            report_lines.append("| وب‌سایت | امتیاز | آخرین تایم‌اوت | وضعیت بازیابی |")
            report_lines.append("| :-------- | :----- | :------------ | :------------ |")
            for item in timed_out_websites_with_scores:
                ws = item['website']
                score = item['score']
                last_timeout_str = item.get("last_timeout")
                last_timeout_dt: Optional[datetime] = datetime.fromisoformat(last_timeout_str) if last_timeout_str else None

                recovery_status = ""
                if last_timeout_dt:
                    time_since_timeout = datetime.now(last_timeout_dt.tzinfo if last_timeout_dt.tzinfo else timezone.utc) - last_timeout_dt
                    if time_since_timeout >= current_settings.TIMEOUT_RECOVERY_DURATION: # از current_settings استفاده شود
                        recovery_status = "آماده بازیابی"
                    else:
                        remaining_time = current_settings.TIMEOUT_RECOVERY_DURATION - time_since_timeout # از current_settings استفاده شود
                        days = remaining_time.days
                        seconds = remaining_time.seconds
                        hours = seconds // 3600
                        minutes = (seconds % 3600) // 60
                        recovery_status = f"{days} روز {hours} ساعت {minutes} دقیقه"
                    report_lines.append(f"| {ws} | {score} | {last_timeout_dt.strftime('%Y-%m-%d %H:%M:%S')} | {recovery_status} |")
                else:
                    report_lines.append(f"| {ws} | {score} | نامشخص | نامشخص |")
        else:
            report_lines.append("هیچ وب‌سایتی در حال حاضر تایم‌اوت نشده است.")
        report_lines.append("\n")


        # تفکیک لینک‌های جمع‌آوری شده بر اساس منبع
        report_lines.append("## ۵. تفکیک لینک‌های جمع‌آوری شده بر اساس منبع")
        if self.source_link_counts:
            for source_type, sources in self.source_link_counts.items():
                report_lines.append(f"\n### ۵.{'۱' if source_type == 'telegram' else '۲'}. منابع {'تلگرام' if source_type == 'telegram' else 'وب‌سایت'}:")
                # مرتب‌سازی منابع بر اساس مجموع لینک‌های جمع‌آوری شده (نزولی)
                sorted_sources = sorted(sources.items(), key=lambda item: sum(item[1].values()), reverse=True)
                
                report_lines.append("| منبع | مجموع لینک‌ها | تفکیک پروتکل |")
                report_lines.append("| :---- | :------------- | :----------- |")
                for source_name, protocols in sorted_sources:
                    total_links_from_source = sum(protocols.values())
                    protocol_details = ", ".join([f"{p}: {c}" for p, c in sorted(protocols.items())])
                    report_lines.append(f"| {source_name} | {total_links_from_source} | {protocol_details} |")
        else:
            report_lines.append("هیچ لینکی از هیچ منبعی جمع‌آوری نشده است.")
        report_lines.append("\n")

        report_lines.append("---")
        report_lines.append("**پایان گزارش.**")
        
        return "\n".join(report_lines)

# ایجاد یک نمونه سراسری از StatsReporter
stats_reporter = StatsReporter()
