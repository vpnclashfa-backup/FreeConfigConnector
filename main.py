# main.py
import asyncio
import os
import json
import sys
from datetime import datetime

# Import necessary modules
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
from src.utils.output_manager import output_manager # Import OutputManager
from src.collectors.telegram_collector import TelegramCollector
from src.collectors.web_collector import WebCollector

async def main_collector_flow():
    print("--- Initializing ConfigConnector ---")

    telegram_collector = None
    web_collector = None
    
    all_collected_links = [] # List to hold all links (dicts) from both sources

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
        traceback.print_exc() # Print full traceback for unexpected errors
    finally:
        # Ensure all collectors are properly closed
        if telegram_collector:
            await telegram_collector.close()
        if web_collector:
            await web_collector.close()

        # Deduplicate all collected links before final save and report
        # The 'link' value in each dict is the unique identifier
        unique_links = {}
        for item in all_collected_links:
            unique_links[item['link']] = item # Use link as key, overwrite if duplicate (keeps last one)
        
        final_unique_links = list(unique_links.values())

        # Save collected links using the new OutputManager
        output_manager.save_configs(final_unique_links) # Use OutputManager to save


        # Finalize SourceManager (save scores and status)
        source_manager.finalize()

        # Generate and print final report
        # Pass initial active counts to stats_reporter
        initial_telegram_channels_count = len(source_manager.get_active_telegram_channels()) # These are already filtered and sorted
        initial_websites_count = len(source_manager.get_active_websites())
        
        # Ensure stats_reporter has the latest unique collected count
        stats_reporter.set_unique_collected(len(final_unique_links)) 
        stats_reporter.end_report() # End report time
        stats_reporter.generate_report(source_manager) # Generate the report with updated counts

        print("--- ConfigConnector Process Completed ---")


if __name__ == "__main__":
    # Start the reporting period (before any collection starts)
    # Load initial sources counts from source_manager after it initializes
    # SourceManager is a global instance, so it's initialized on import.
    initial_telegram_channels_count = len(source_manager.get_active_telegram_channels())
    initial_websites_count = len(source_manager.get_active_websites())
    stats_reporter.start_report(initial_telegram_channels_count, initial_websites_count)

    # Run the main asynchronous flow
    try:
        asyncio.run(main_collector_flow())
    except KeyboardInterrupt:
        print("\nMain: Program interrupted by user (Ctrl+C). Exiting gracefully.")
        # Ensure finalize and report are still run even on interrupt
        source_manager.finalize()
        stats_reporter.end_report() # End report time on interrupt
        stats_reporter.generate_report(source_manager)
    except Exception as e:
        print(f"Main: A critical error occurred in main execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) # Exit with an error code

