import asyncio
import os
import json
import sys
from datetime import datetime
from typing import List, Dict, Optional 
import logging # Import the logging module

# Import necessary modules
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
from src.utils.output_manager import OutputManager # Corrected to import the class directly
from src.collectors.telegram_collector import TelegramCollector
from src.collectors.web_collector import WebCollector
from src.utils.logging_config import setup_logging # Import the logging setup

# --- Setup Logging (should be done once at the very beginning of the script execution) ---
# Ensure OUTPUT_DIR exists before setting up logging
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
LOG_FILE = os.path.join(settings.OUTPUT_DIR, "error_warnings.log")
setup_logging(LOG_FILE)

# Get a logger instance for main.py 
logger = logging.getLogger(__name__)
# --- End Setup Logging ---


async def main_collector_flow():
    logger.info("--- Initializing ConfigConnector ---")

    telegram_collector: Optional[TelegramCollector] = None
    web_collector: Optional[WebCollector] = None

    all_collected_links: List[Dict] = [] # List to hold all links (dicts) from both sources

    try:
        # Initialize and run Telegram Collector
        logger.info("\n--- Starting Telegram Link Collection (Web Scraping) ---")
        telegram_collector = TelegramCollector()
        collected_links_from_telegram = await telegram_collector.collect_from_telegram()
        all_collected_links.extend(collected_links_from_telegram)
        logger.info("--- Telegram Link Collection Finished ---")

        # Initialize and run Web Collector
        web_collector = WebCollector()
        logger.info("\n--- Starting Web Link Collection ---")
        collected_links_from_web = await web_collector.collect_from_web() # Corrected method name as per WebCollector implementation
        all_collected_links.extend(collected_links_from_web)
        logger.info("--- Web Link Collection Finished ---")

    except Exception as e:
        logger.error(f"Main: An unhandled error occurred during collection process: {e}")
        # import traceback is already at the top level in __main__ block
        logger.error(traceback.format_exc()) # Log the full traceback to the file
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
        # Instantiate OutputManager correctly and call its async method
        output_manager_instance = OutputManager(final_unique_links) 
        await output_manager_instance.save_all_configs() # Call the async method

        # Finalize SourceManager (save scores and status)
        source_manager.save_sources() # This is the correct method call as per your SourceManager


        # Generate and print final report
        # The stats_reporter.start_report is called in __main__ block with initial counts
        # and datetime.now() for start_time.
        # stats_reporter.end_report expects end_time and total_unique_links.
        stats_reporter.end_report(datetime.now(), len(final_unique_links)) 
        
        # Now generate the report content after end_report has updated internal stats.
        markdown_report_content = stats_reporter.generate_report(source_manager) 
        logger.info("\n" + "-"*50)
        logger.info("Generated Report (Full details in report.md):")
        logger.info(markdown_report_content) # Log the report content via logger
        logger.info("-" * 50 + "\n")

        try:
            report_file_path = settings.REPORT_FILE
            os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
            with open(report_file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_report_content)
            logger.info(f"Collection report saved to: {report_file_path}")
        except Exception as e:
            logger.error(f"Main: Error saving report file: {e}")
            logger.error(traceback.format_exc()) # Log traceback for this error

        logger.info("--- ConfigConnector Process Completed ---")


if __name__ == "__main__":
    # Add current working directory to Python path if not already there
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())

    # The _ = source_manager line ensures it's initialized (due to its singleton pattern)
    # and loads sources as part of its __init__ (if not already loaded).
    _ = source_manager 

    # Load initial sources as soon as source_manager is ready (if not already loaded by singleton)
    # Calling it explicitly here ensures it's done before getting counts.
    source_manager.load_sources() 

    initial_telegram_channels_count = len(source_manager.get_active_telegram_channels())
    initial_websites_count = len(source_manager.get_active_websites())
    
    # Start report with initial counts and current time
    stats_reporter.start_report(datetime.now(), initial_telegram_channels_count, initial_websites_count) 

    try:
        asyncio.run(main_collector_flow())
    except KeyboardInterrupt:
        logger.warning("\nMain: Program interrupted by user (Ctrl+C). Exiting gracefully.")
        # Ensure finalization and report generation on interrupt
        source_manager.save_sources() # Save current state on interrupt
        stats_reporter.end_report(datetime.now(), stats_reporter.get_total_unique_collected()) # Ensure end_time and final count are passed
        markdown_report_content = stats_reporter.generate_report(source_manager)
        report_file_path = settings.REPORT_FILE
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_report_content)
        logger.info(f"Main: Collection report saved to: {report_file_path} (on interrupt)")
        logger.info("--- ConfigConnector Process Completed (Interrupted) ---")
        sys.exit(0) # Exit cleanly
    except Exception as e:
        logger.critical(f"Main: A critical error occurred in main execution: {e}") # Use critical for unhandled top-level errors
        import traceback # Import traceback here if not imported globally
        logger.critical(traceback.format_exc()) # Log full traceback
        # Ensure finalization and report generation on critical error
        source_manager.save_sources() # Save current state on critical error
        stats_reporter.end_report(datetime.now(), stats_reporter.get_total_unique_collected()) # Ensure end_time and final count are passed
        markdown_report_content = stats_reporter.generate_report(source_manager)
        report_file_path = settings.REPORT_FILE
        os.makedirs(os.path.dirname(report_file_path), exist_ok=True)
        with open(report_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_report_content)
        logger.info(f"Main: Collection report saved to: {report_file_path} (on critical error)")
        logger.info("--- ConfigConnector Process Completed (with Critical Error) ---")
        sys.exit(1) # Exit with error code