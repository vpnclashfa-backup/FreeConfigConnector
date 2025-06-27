# src/collectors/web_collector.py

import httpx # نیاز به نصب: pip install httpx
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
from src.parsers.config_parser import ConfigParser
import asyncio
import traceback

class WebCollector:
    def __init__(self):
        self.config_parser = ConfigParser()
        self.client = httpx.AsyncClient(timeout=settings.COLLECTION_TIMEOUT_SECONDS)
        print("WebCollector initialized.")

    async def _fetch_url_content(self, url):
        """Fetches content from a given URL."""
        try:
            # Add a User-Agent header to mimic a browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = await self.client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status() # Raise an exception for 4xx/5xx responses
            return response.text
        except httpx.TimeoutException:
            print(f"WebCollector: Timeout fetching {url}")
            source_manager.update_website_score(url, -settings.COLLECTION_TIMEOUT_SECONDS) # Decrease score on timeout
            return None
        except httpx.RequestError as e:
            print(f"WebCollector: Request error fetching {url}: {e}")
            source_manager.update_website_score(url, -5) # Decrease score on other request errors
            return None
        except Exception as e:
            print(f"WebCollector: An unexpected error occurred fetching {url}: {e}")
            source_manager.update_website_score(url, -10) # Decrease score on unexpected errors
            return None

    async def collect_from_website(self, url):
        """Collects config links from a single website URL."""
        print(f"WebCollector: Collecting from website: {url}")
        content = await self._fetch_url_content(url)
        collected_links = []

        if content:
            parsed_links = self.config_parser.parse_content(content)
            for link_info in parsed_links:
                protocol = link_info.get('protocol', 'unknown')
                link = link_info.get('link')

                if link and protocol in settings.ACTIVE_PROTOCOLS:
                    collected_links.append(link)
                    stats_reporter.increment_total_collected()
                    stats_reporter.increment_protocol_count(protocol)
                    stats_reporter.record_source_link("web", url, protocol)
                    print(f"  WebCollector: Found {protocol} link: {link}")
                    # If a link is successfully found and parsed, increase score
                    source_manager.update_website_score(url, 1) # Small positive score for successful extraction
                elif link and protocol == 'subscription': # Handle subscription URLs for further collection
                    print(f"  WebCollector: Found subscription URL: {link}. Adding for further collection.")
                    source_manager.add_website(link) # Add subscription URL as a new website to collect from
                    source_manager.update_website_score(url, 2) # Slightly higher score for discovering new source
                elif settings.IGNORE_UNPARSEABLE_CONTENT:
                    print(f"  WebCollector: Ignored unparseable content from {url}.")
                else:
                    print(f"  WebCollector: Could not parse content from {url} or protocol not active. Content snippet: {content[:100]}...")
                    source_manager.update_website_score(url, -1) # Small negative score for unparseable content

        if not collected_links and content: # If content was fetched but no links were found/parsed
             source_manager.update_website_score(url, -2) # Small negative score if content fetched but no valid links

        return collected_links

    async def collect_from_websites(self):
        """Main method to collect from all active websites."""
        all_collected_links = []
        active_websites = source_manager.get_active_websites()
        print(f"\nWebCollector: Starting collection from {len(active_websites)} active websites.")

        tasks = [self.collect_from_website(url) for url in active_websites]
        results = await asyncio.gather(*tasks, return_exceptions=True) # Collect results and exceptions

        for i, result in enumerate(results):
            url = active_websites[i]
            if isinstance(result, Exception):
                print(f"WebCollector: Error collecting from {url}: {result}")
                traceback.print_exc()
                source_manager.update_website_score(url, -10) # Significant score reduction for unhandled exceptions
            elif result:
                all_collected_links.extend(result)

        # Record newly timed-out websites for the report
        for website, data in source_manager.timeout_websites.items():
            # Check if this website was active at the start of collection and is now timed out
            if website in active_websites and source_manager._is_timed_out_website(website):
                stats_reporter.add_newly_timed_out_website(website)

        print(f"WebCollector: Finished collection. Total links from web: {len(all_collected_links)}")
        return all_collected_links

    async def close(self):
        """Closes the HTTP client session."""
        await self.client.aclose()
        print("WebCollector client closed.")
