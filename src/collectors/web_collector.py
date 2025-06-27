# src/collectors/web_collector.py

import httpx
import re
import os
import json
import asyncio
import traceback
from typing import Optional, List, Dict # NEW: Import Optional, List, Dict for type hints
    
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
            source_manager.update_website_score(url, -settings.COLLECTION_TIMEOUT_SECONDS) # Decrease score on timeout
            return None
        except httpx.HTTPStatusError as e:
            # Handle 404 (Not Found), 403 (Forbidden), etc.
            print(f"WebCollector: HTTP Error {e.response.status_code} fetching {url}: {e.response.text.strip()[:100]}...")
            if e.response.status_code == 404: # Not Found - may indicate dead link
                source_manager.update_website_score(url, -50) # Strong penalty
            elif e.response.status_code == 429: # Too Many Requests (Rate Limit)
                print(f"WebCollector: Rate limit hit for {url}. Consider increasing delay or using proxies.")
                source_manager.update_website_score(url, -30) # Strong penalty
            else:
                source_manager.update_website_score(url, -10) # General HTTP error penalty
            return None
        except httpx.RequestError as e:
            print(f"WebCollector: Request error fetching {url}: {e}")
            source_manager.update_website_score(url, -15) # Decrease score on other request errors
            return None
        except Exception as e:
            print(f"WebCollector: An unexpected error occurred fetching {url}: {e}")
            source_manager.update_website_score(url, -20) # Decrease score on unexpected errors
            return None

    def _get_raw_github_url(self, github_url: str) -> str:
        """
        Converts a regular GitHub URL (blob) to its raw content URL.
        Example: https://github.com/user/repo/blob/main/file.txt
        becomes: https://raw.githubusercontent.com/user/repo/main/file.txt
        """
        if "github.com" in github_url and "/blob/" in github_url:
            raw_url = github_url.replace("github.com", "raw.githubusercontent.com")
            raw_url = raw_url.replace("/blob/", "/")
            return raw_url
        return github_url # Return original if not a recognizable GitHub blob URL

    async def _discover_and_add_website(self, url: str):
        """
        Discovers a new website URL and adds it to the SourceManager if enabled.
        """
        # We standardize and validate URLs in source_manager
        if settings.ENABLE_CONFIG_LINK_DISCOVERY: # Using ENABLE_CONFIG_LINK_DISCOVERY for generic URL discovery
            if source_manager.add_website(url):
                stats_reporter.increment_discovered_website_count()
                print(f"WebCollector: Discovered and added new website URL: {url}")
        
    async def collect_from_website(self, url: str) -> List[Dict]:
        """
        Collects config links from a single website URL, parses content, and updates stats.
        """
        processed_url = self._get_raw_github_url(url)
        content = await self._fetch_url_content(processed_url)
        collected_links = []

        if not content:
            print(f"WebCollector: No content fetched for {url}. Skipping parsing.")
            return []

        # Use ConfigParser to parse the content
        parsed_links_info = self.config_parser.parse_content(content)
        
        if not parsed_links_info and not settings.IGNORE_UNPARSEABLE_CONTENT:
            print(f"WebCollector: Could not parse any links from {url}. Content snippet: {content[:100]}...")
            source_manager.update_website_score(url, -2) # Small negative score if content fetched but no valid links
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
                # print(f"  WebCollector: Found {protocol} link: {link}")
                source_manager.update_website_score(url, 1) # Small positive score for successful extraction
            elif protocol == 'subscription':
                # If a subscription link is found, add it as a new website source
                print(f"WebCollector: Found subscription URL: {link}. Attempting to add as a new source.")
                await self._discover_and_add_website(link)
                source_manager.update_website_score(url, 2) # Slightly higher score for discovering new source
            else: # Protocol not active or unknown, but it's a valid link found by parser
                # print(f"WebCollector: Found link with inactive/unknown protocol ({protocol}): {link}. Skipping.")
                pass # Don't add to collected_links if protocol is not active


        # At the end of processing a URL, if any links were found, give a positive score
        if collected_links:
            source_manager.update_website_score(url, 5) # More substantial positive score for overall success

        return collected_links

    async def collect_from_websites(self) -> List[Dict]:
        """Main method to collect from all active websites."""
        all_collected_links = []
        active_websites = source_manager.get_active_websites() # Get active and sorted websites
        print(f"\nWebCollector: Starting collection from {len(active_websites)} active websites.")

        if not active_websites:
            print("WebCollector: No active websites to process.")
            return []

        # Process websites in parallel
        tasks = []
        for url in active_websites:
            # Dynamic delay for web sources could be implemented here based on score
            # For now, relying on httpx timeout and error handling.
            # current_score = source_manager._all_website_scores.get(url, 0)
            # base_delay = 0.5 # seconds, smaller for web generally
            # delay_multiplier = 1 + max(0, -current_score * 0.1) # Potentially higher impact for web
            # await asyncio.sleep(base_delay * delay_multiplier)
            tasks.append(self.collect_from_website(url))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            url = active_websites[i]
            if isinstance(result, Exception):
                print(f"WebCollector: Error processing website {url}: {result}")
                traceback.print_exc()
                source_manager.update_website_score(url, -20) # Penalize for unhandled exceptions
            elif result:
                all_collected_links.extend(result)
        
        # Record newly timed-out websites for the report
        for website_name, data in source_manager.timeout_websites.items():
            if website_name in active_websites and source_manager._is_timed_out_website(website_name):
                stats_reporter.add_newly_timed_out_website(website_name)

        print(f"WebCollector: Finished collection. Total links from web: {len(all_collected_links)}")
        return all_collected_links

    async def close(self):
        """Closes the HTTP client session."""
        await self.client.aclose()
        print("WebCollector client closed.")

