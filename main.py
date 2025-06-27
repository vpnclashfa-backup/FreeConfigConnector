# main.py
import asyncio
import os
import json
import sys
from datetime import datetime
from typing import List, Dict, Optional # Added Optional, List, Dict

# Import necessary modules
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
from src.utils.output_manager import output_manager
from src.collectors.telegram_collector import TelegramCollector
from src.collectors.web_collector import WebCollector

async def main_collector_flow():
    print("--- Initializing ConfigConnector ---")

    telegram_collector: Optional[TelegramCollector] = None
    web_collector: Optional[WebCollector] = None
    
    all_collected_links: List[Dict] = [] # List to hold all links (dicts) from both sources

    try:
        # Initialize and run Telegram Collector
        print("\n--- Starting Telegram Link Collection (Web Scraping) ---")
        telegram_collector = TelegramCollector()
        collected_links_from_telegram = await telegram_collector.collect_from_telegram()
        all_collected_links.extend(collected_links_from_telegram)
        print("--- Telegram Link Collection Finished ---")
        
        # Initialize and run Web Collector
        web_collector = WebCollector()
        print("\n--- Starting Web Link Collection ---")
        collected_links_from_web = await web_collector.collect_from_websites()
        all_collected_links.extend(collected_links_from_web)
        print("--- Web Link Collection Finished ---")

    except Exception as e:
        print(f"Main: An unhandled error occurred during collection process: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure all collectors are properly closed
        if telegram_collector:
            await telegram_collector.close()
        if web_collector:
            await web_collector.close()

        # Deduplicate all collected links before final save and report
        unique_links: Dict[str, Dict] = {}
        for item in all_collected_links:
            unique_links[item['link']] = item
        
        final_unique_links: List[Dict] = list(unique_links.values())

        # Save collected links using the OutputManager
        output_manager.save_configs(final_unique_links)


        # Finalize SourceManager (save scores and status)
        source_manager.finalize()

        # Generate and print final report
        # These counts are already handled by stats_reporter.start_report call in __main__
        stats_reporter.set_unique_collected(len(final_unique_links))
        stats_reporter.end_report() 
        
        # NEW: Generate Markdown report content
        markdown_report_content = stats_reporter.generate_report(source_manager)
        print("\n" + "-"*50)
        print("Generated Report (Full details in report.md):")
        print(markdown_report_content) # Also print to console for immediate feedback
        print("-" * 50 + "\n")

        # NEW: Save Markdown report to file
        try:
            report_file_path = settings.REPORT_FILE
            os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
            with open(report_file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_report_content)
            print(f"Main: Collection report saved to: {report_file_path}")
        except Exception as e:
            print(f"Main: Error saving report file: {e}")

        print("--- ConfigConnector Process Completed ---")


if __name__ == "__main__":
    # Ensure source_manager is initialized to get initial counts for stats_reporter
    # This also loads existing data like timeout lists
    _ = source_manager # Accessing it ensures it's initialized

    # Start the reporting period (before any collection starts)
    initial_telegram_channels_count = len(source_manager.get_active_telegram_channels())
    initial_websites_count = len(source_manager.get_active_websites())
    stats_reporter.start_report(initial_telegram_channels_count, initial_websites_count)
    
    try:
        asyncio.run(main_collector_flow())
    except KeyboardInterrupt:
        print("\nMain: Program interrupted by user (Ctrl+C). Exiting gracefully.")
        source_manager.finalize()
        stats_reporter.end_report()
        markdown_report_content = stats_reporter.generate_report(source_manager)
        report_file_path = settings.REPORT_FILE
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_report_content)
        print(f"Main: Collection report saved to: {report_file_path} (on interrupt)")
        print("--- ConfigConnector Process Completed (Interrupted) ---")
    except Exception as e:
        print(f"Main: A critical error occurred in main execution: {e}")
        import traceback
        traceback.print_exc()
        source_manager.finalize()
        stats_reporter.end_report()
        markdown_report_content = stats_reporter.generate_report(source_manager)
        report_file_path = settings.REPORT_FILE
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_report_content)
        print(f"Main: Collection report saved to: {report_file_path} (on critical error)")
        print("--- ConfigConnector Process Completed (with Critical Error) ---")
        sys.exit(1)
