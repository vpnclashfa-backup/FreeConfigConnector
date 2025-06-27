# src/collectors/web_collector.py

import httpx
import re # Not directly used in this version, but can be kept for future
import os # Not directly used in this version, but can be kept for future
import json # Not directly used in this version, but can be kept for future
import asyncio
import traceback
from typing import Optional, List, Dict # Ensure all necessary types are imported
    
from src.utils.settings_manager import settings
from src.utils.source_manager import source_manager
from src.utils.stats_reporter import stats_reporter
from src.parsers.config_parser import ConfigParser # Import ConfigParser

class WebCollector:
    def __init__(self):
        self.config_parser = ConfigParser()
        self.client = httpx.AsyncClient(timeout=settings.COLLECTION_TIMEOUT_SECONDS)
        print("WebCollector initialized.")

    async def _fetch_url_content(self, url: str) -> Optional[str]:
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
            source_manager.update_website_score(url, -settings.COLLECTION_TIMEOUT_SECONDS)
            return None
        except httpx.HTTPStatusError as e:
            print(f"WebCollector: HTTP Error {e.response.status_code} fetching {url}: {e.response.text.strip()[:100]}...")
            if e.response.status_code == 404:
                source_manager.update_website_score(url, -50)
            elif e.response.status_code == 429:
                print(f"WebCollector: Rate limit hit for {url}. Consider increasing delay or using proxies.")
                source_manager.update_website_score(url, -30)
            else:
                source_manager.update_website_score(url, -10)
            return None
        except httpx.RequestError as e:
            print(f"WebCollector: Request error fetching {url}: {e}")
            source_manager.update_website_score(url, -15)
            return None
        except Exception as e:
            print(f"WebCollector: An unexpected error occurred fetching {url}: {e}")
            source_manager.update_website_score(url, -20)
            return None

    def _get_raw_github_url(self, github_url: str) -> str:
        """
        Converts a regular GitHub URL (blob) to its raw content URL.
        """
        if "github.com" in github_url and "/blob/" in github_url:
            raw_url = github_url.replace("github.com", "raw.githubusercontent.com")
            raw_url = raw_url.replace("/blob/", "/")
            return raw_url
        return github_url

    async def _discover_and_add_website(self, url: str):
        """
        Discovers a new website URL and adds it to the SourceManager if enabled.
        """
        if settings.ENABLE_CONFIG_LINK_DISCOVERY:
            if source_manager.add_website(url):
                stats_reporter.increment_discovered_website_count()
                print(f"WebCollector: Discovered and added new website URL: {url}")
        
    async def collect_from_website(self, url: str) -> List[Dict]:
        """
        Collects config links from a single website URL, parses content, and updates stats.
        """
        processed_url = self._get_raw_github_url(url)
        content = await self._fetch_url_content(processed_url)
        collected_links: List[Dict] = []

        if not content:
            print(f"WebCollector: No content fetched for {url}. Skipping parsing.")
            return []

        parsed_links_info: List[Dict] = self.config_parser.parse_content(content)
        
        if not parsed_links_info and not settings.IGNORE_UNPARSEABLE_CONTENT:
            print(f"WebCollector: Could not parse any links from {url}. Content snippet: {content[:100]}...")
            source_manager.update_website_score(url, -2)
        elif not parsed_links_info and settings.IGNORE_UNPARSEABLE_CONTENT:
            print(f"WebCollector: No links parsed from {url}. Ignoring unparseable content as per settings.")


        for link_info in parsed_links_info:
            protocol = link_info.get('protocol', 'unknown')
            link = link_info.get('link')
            
            if not link:
                continue

            if protocol in settings.ACTIVE_PROTOCOLS:
                collected_links.append(link_info)
                stats_reporter.increment_total_collected()
                stats_reporter.increment_protocol_count(protocol)
                stats_reporter.record_source_link("web", url, protocol)
                source_manager.update_website_score(url, 1)
            elif protocol == 'subscription':
                print(f"WebCollector: Found subscription URL: {link}. Attempting to add as a new source.")
                await self._discover_and_add_website(link)
                source_manager.update_website_score(url, 2)
            else:
                pass # Link found but protocol is not active or is unknown


        if collected_links:
            source_manager.update_website_score(url, 5)

        return collected_links

    async def collect_from_websites(self) -> List[Dict]:
        """Main method to collect from all active websites."""
        all_collected_links: List[Dict] = []
        active_websites: List[str] = source_manager.get_active_websites()

        if not active_websites:
            print("WebCollector: No active websites to process.")
            return []

        tasks = []
        for url in active_websites:
            tasks.append(self.collect_from_website(url))
        
        results: List[Exception | List[Dict]] = await asyncio.gather(*tasks, return_exceptions=True) # Explicitly type results

        for i, result in enumerate(results):
            url = active_websites[i]
            if isinstance(result, Exception):
                print(f"WebCollector: Error processing website {url}: {result}")
                traceback.print_exc()
                source_manager.update_website_score(url, -20)
            elif result: # result is List[Dict] here
                all_collected_links.extend(result)
        
        # Check for newly timed-out websites after processing all
        for website_name in list(source_manager.timeout_websites.keys()):
            if website_name in active_websites and source_manager._all_website_scores.get(website_name, 0) <= settings.MAX_TIMEOUT_SCORE_WEB:
                stats_reporter.add_newly_timed_out_website(website_name)

        print(f"WebCollector: Finished collection. Total links from web: {len(all_collected_links)}")
        return all_collected_links

    async def close(self):
        """Closes the HTTP client session."""
        await self.client.aclose()
        print("WebCollector client closed.")

