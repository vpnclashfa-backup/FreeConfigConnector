# main.py
import asyncio
import os
import json
import sys

# Import necessary modules
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
from src.collectors.telegram_collector import TelegramCollector
from src.collectors.web_collector import WebCollector

async def main_collector_flow():
    print("--- Initializing ConfigConnector ---")

    # Initialize collectors
    telegram_collector = None
    web_collector = None

    all_collected_links = [] # List to hold all links from both sources

    try:
        # Initialize and run Telegram Collector
        if settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH:
            telegram_collector = TelegramCollector(settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            try:
                await telegram_collector.connect()
                print("\n--- Starting Telegram Link Collection ---")
                collected_links_from_telegram = await telegram_collector.collect_from_telegram()
                all_collected_links.extend(collected_links_from_telegram)
                print("--- Telegram Link Collection Finished ---")
            except Exception as e:
                print(f"Main: Error during Telegram collection: {e}")
                # In case of critical errors, ensure we still try to run web collector
        else:
            print("Main: Telegram API credentials not set. Skipping Telegram collection.")

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
        unique_links = {}
        for item in all_collected_links:
            unique_links[item['link']] = item # Use link as key, overwrite if duplicate (keeps last one)

        final_unique_links = list(unique_links.values())

        # Save combined unique links to output file
        output_dir = settings.OUTPUT_DIR_NAME # Use directory name from settings
        os.makedirs(os.path.join(settings.PROJECT_ROOT, output_dir), exist_ok=True) # Ensure output dir exists
        output_file_path = settings.COLLECTED_LINKS_FILE

        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                json.dump(final_unique_links, f, indent=4, ensure_ascii=False)
            print(f"\nMain: All collected unique links saved to: {output_file_path}")
        except Exception as e:
            print(f"Main: Error saving collected links to file: {e}")

        # Finalize SourceManager (save scores and status)
        source_manager.finalize()

        # Generate and print final report
        stats_reporter.set_unique_collected(len(final_unique_links)) # Set unique count before reporting
        stats_reporter.generate_report(source_manager)

        print("--- ConfigConnector Process Completed ---")


if __name__ == "__main__":
    # Start the reporting period (before any collection starts)
    initial_telegram_channels = len(source_manager.get_active_telegram_channels())
    initial_websites = len(source_manager.get_active_websites())
    stats_reporter.start_report(initial_telegram_channels, initial_websites)

    # Run the main asynchronous flow
    try:
        asyncio.run(main_collector_flow())
    except KeyboardInterrupt:
        print("\nMain: Program interrupted by user (Ctrl+C). Exiting gracefully.")
        # Ensure finalize and report are still run even on interrupt
        source_manager.finalize()
        stats_reporter.generate_report(source_manager)
    except Exception as e:
        print(f"Main: A critical error occurred in main execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) # Exit with an error code
