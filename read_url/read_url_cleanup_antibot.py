#!/usr/bin/env python3

import json
import sys
import argparse
import re
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

import requests
from readability import Document
from bs4 import BeautifulSoup
import html2text

try:
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CrawlerRunConfig,
        CacheMode,
        UndetectedAdapter
    )
    from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    print("⚠️  crawl4ai is not installed. To use anti-bot modes, run: pip install crawl4ai")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebToMarkdownConverter:
    def __init__(
        self,
        delay: float = 1.0,
        timeout: int = 30,
        use_antibot: bool = False,
        antibot_mode: str = "stealth",
        headless: bool = True
    ):
        self.delay = delay
        self.timeout = timeout
        self.use_antibot = use_antibot and CRAWL4AI_AVAILABLE
        self.antibot_mode = antibot_mode
        self.headless = headless

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = True
        self.h2t.ignore_images = True
        self.h2t.ignore_emphasis = False
        self.h2t.body_width = 0
        self.h2t.unicode_snob = True
        self.h2t.decode_errors = 'ignore'

        if use_antibot and not CRAWL4AI_AVAILABLE:
            logger.warning("Antibot mode requested, but crawl4ai is not installed. Normal mode is used.")

    async def fetch_url_with_antibot(self, url: str) -> Optional[str]:
        if not CRAWL4AI_AVAILABLE:
            logger.error("crawl4ai not installed")
            return None

        try:
            logger.info(f"Download URL using antibot ({self.antibot_mode}): {url}")

            browser_config = BrowserConfig(
                headless=self.headless,
                verbose=True
            )

            if self.antibot_mode == "stealth":
                browser_config.enable_stealth = True
                crawler_strategy = None

            elif self.antibot_mode == "undetected":
                adapter = UndetectedAdapter()
                crawler_strategy = AsyncPlaywrightCrawlerStrategy(
                    browser_config=browser_config,
                    browser_adapter=adapter
                )

            elif self.antibot_mode == "combined":
                # stealth + undetected
                browser_config.enable_stealth = True
                adapter = UndetectedAdapter()
                crawler_strategy = AsyncPlaywrightCrawlerStrategy(
                    browser_config=browser_config,
                    browser_adapter=adapter
                )
            else:
                logger.warning(f"Unknown mode antibot: {self.antibot_mode}. Using stealth.")
                browser_config.enable_stealth = True
                crawler_strategy = None

            crawl_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=self.timeout * 1000
            )

            if crawler_strategy:
                async with AsyncWebCrawler(
                    crawler_strategy=crawler_strategy,
                    config=browser_config
                ) as crawler:
                    result = await crawler.arun(url=url, config=crawl_config)
            else:
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    result = await crawler.arun(url=url, config=crawl_config)

            if result and result.success:
                logger.info(f"✓ Successfully downloaded: {url}")
                return result.html
            else:
                logger.error(f"✗ Error while loading {url}: {result.error_message if result else 'Unknown'}")
                return None

        except Exception as e:
            logger.error(f"Error when loading using antibot {url}: {e}")
            return None

    def fetch_url(self, url: str) -> Optional[str]:
        try:
            logger.info(f"Downloading URL (requests): {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error during downloading {url}: {e}")
            return None

    def extract_content(self, html: str, url: str = None) -> Dict[str, str]:
        try:
            doc = Document(html)

            title = doc.title()
            content_html = doc.summary()

            soup = BeautifulSoup(content_html, 'html.parser')

            for tag in soup.find_all([
                'script', 'style', 'nav', 'aside', 'footer',
                'header', 'figcaption', 'iframe', 'frame',
                'object', 'embed', 'applet'
            ]):
                tag.decompose()

            for tag in soup.find_all(True):
                tag.attrs = {k: v for k, v in tag.attrs.items()
                           if k in ['href', 'src', 'alt', 'title']}

            if url:
                for link in soup.find_all('a', href=True):
                    link['href'] = urljoin(url, link['href'])
                for img in soup.find_all('img', src=True):
                    img['src'] = urljoin(url, img['src'])

            cleaned_html = str(soup)
            markdown = self.h2t.handle(cleaned_html)

            markdown = self._clean_markdown(markdown)

            return {
                'title': title.strip() if title else '',
                'content': markdown.strip()
            }

        except Exception as e:
            logger.error(f"Error retrieving content: {e}")
            return {'title': '', 'content': ''}

    def _clean_markdown(self, markdown: str) -> str:
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        markdown = re.sub(r'\[\]\(\)', '', markdown)

        lines = [line.rstrip() for line in markdown.split('\n')]
        markdown = '\n'.join(lines)

        return markdown.strip()

    async def process_single_url_async(self, url_data: Dict) -> Optional[Dict]:
        url = url_data.get('link')
        if not url:
            logger.warning("Missing URL in data")
            return None

        html = await self.fetch_url_with_antibot(url)
        if not html:
            logger.warning(f"Failed to load {url}")
            return None

        extracted = self.extract_content(html, url)

        if not extracted['content']:
            logger.warning(f"Unable to retrieve content from {url}")
            return None

        result = {
            "creator": url_data.get('creator', url_data.get('dc:creator', '')),
            "title": extracted['title'] or url_data.get('title', ''),
            "link": url,
            "pubDate": url_data.get('pubDate', ''),
            "dc:creator": url_data.get('dc:creator', url_data.get('creator', '')),
            "content": extracted['content'],
            "contentSnippet": url_data.get('contentSnippet', ''),
            "guid": url_data.get('guid', ''),
            "categories": url_data.get('categories', []),
            "isoDate": url_data.get('isoDate', '')
        }

        return result

    def process_single_url(self, url_data: Dict) -> Optional[Dict]:
        url = url_data.get('link')
        if not url:
            logger.warning("Missing URL in data")
            return None

        html = self.fetch_url(url)
        if not html:
            logger.warning(f"Failed to load {url}")
            return None

        extracted = self.extract_content(html, url)

        if not extracted['content']:
            logger.warning(f"Unable to retrieve content from {url}")
            return None

        result = {
            "creator": url_data.get('creator', url_data.get('dc:creator', '')),
            "title": extracted['title'] or url_data.get('title', ''),
            "link": url,
            "pubDate": url_data.get('pubDate', ''),
            "dc:creator": url_data.get('dc:creator', url_data.get('creator', '')),
            "content": extracted['content'],
            "contentSnippet": url_data.get('contentSnippet', ''),
            "guid": url_data.get('guid', ''),
            "categories": url_data.get('categories', []),
            "isoDate": url_data.get('isoDate', '')
        }

        return result

    async def process_urls_async(self, url_list: List[Dict]) -> List[Dict]:
        results = []

        for i, url_data in enumerate(url_list):
            logger.info(f"Processing {i+1}/{len(url_list)}: {url_data.get('link', 'No URL')}")

            result = await self.process_single_url_async(url_data)
            if result:
                results.append(result)

            if i < len(url_list) - 1:
                await asyncio.sleep(self.delay)

        return results

    def process_urls(self, url_list: List[Dict]) -> List[Dict]:
        results = []

        for i, url_data in enumerate(url_list):
            logger.info(f"Processing {i+1}/{len(url_list)}: {url_data.get('link', 'No URL')}")

            result = self.process_single_url(url_data)
            if result:
                results.append(result)

            if i < len(url_list) - 1:
                time.sleep(self.delay)

        return results

    def get_cleaned_content_dict(self, url_data: Union[Dict, List[Dict]]) -> Union[Dict, List[Dict]]:
        if self.use_antibot:
            if isinstance(url_data, list):
                return asyncio.run(self.process_urls_async(url_data))
            else:
                return asyncio.run(self.process_single_url_async(url_data))
        else:
            if isinstance(url_data, list):
                return self.process_urls(url_data)
            else:
                return self.process_single_url(url_data)

    def save_results(self, results: Union[Dict, List[Dict]], output_file: str = None):
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"cleaned_content_{timestamp}.json"

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            logger.info(f"Results saved to {output_file}")

        except Exception as e:
            logger.error(f"Error during saving results: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Converter of web pages into cleaned content with support for anti-bot modes'
    )
    parser.add_argument('data', help='JSON string with data for processing')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests')
    parser.add_argument('--output', type=str, help='File for saving results')
    parser.add_argument('--print-json', action='store_true', help='Output the result in JSON format')

    parser.add_argument('--antibot', action='store_true', help='Use anti-bot system bypass modes')
    parser.add_argument(
        '--antibot-mode',
        type=str,
        choices=['stealth', 'undetected', 'combined'],
        default='stealth',
        help='Anti-bot mode: stealth (fast), undetected (advanced), combined (godmode)'
    )
    parser.add_argument('--no-headless', action='store_true', help='Show browser window (not headless)')

    args = parser.parse_args()

    try:
        input_data = json.loads(args.data)

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}", file=sys.stderr)
        print('Example: python3 script.py \'{"title": "Test", "link": "https://example.com"}\'', file=sys.stderr)
        sys.exit(1)

    converter = WebToMarkdownConverter(
        delay=args.delay,
        use_antibot=args.antibot,
        antibot_mode=args.antibot_mode,
        headless=not args.no_headless
    )

    try:
        results = converter.get_cleaned_content_dict(input_data)

        if results:
            if args.print_json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                if isinstance(results, list):
                    print(f"Processed {len(results)} articles")
                    for i, result in enumerate(results):
                        title = result.get('title', 'No title')[:100]
                        content_len = len(result.get('content', ''))
                        print(f"{i+1}. {title}... ({content_len} symbols)")
                else:
                    title = results.get('title', 'No title')[:100]
                    content_len = len(results.get('content', ''))
                    print(f"Article processed: {title}... ({content_len} symbols)")

            if args.output:
                converter.save_results(results, args.output)

        else:
            print("No pages could be processed.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


"""
**USAGE EXAMPLES:**

1. **Normal mode (via `requests`):**
python script.py '{"title": "Example", "link": "https://example.com"}'

2. **Stealth mode (basic protection):**
python script.py '{"title": "Example", "link": "https://example.com"}' --antibot --antibot-mode stealth

3. **Undetected mode (advanced protection):**
python script.py '{"title": "Example", "link": "https://example.com"}' --antibot --antibot-mode undetected

4. **Combined mode (maximum protection):**
python script.py '{"title": "Example", "link": "https://example.com"}' --antibot --antibot-mode combined

5. **With visible browser (for debugging):**
python script.py '{"title": "Example", "link": "https://example.com"}' --antibot --no-headless

6. **Processing a list of URLs:**
python script.py '[{"link": "https://site1.com"}, {"link": "https://site2.com"}]' --antibot --output results.json

7. **Using in code:**
from web_converter import WebToMarkdownConverter

# Without antibot
converter = WebToMarkdownConverter()
result = converter.get_cleaned_content_dict({"link": "https://example.com"})

# With antibot (stealth mode)
converter = WebToMarkdownConverter(use_antibot=True, antibot_mode="stealth")
result = converter.get_cleaned_content_dict({"link": "https://protected-site.com"})

# With antibot (combined mode – maximum protection)
converter = WebToMarkdownConverter(
    use_antibot=True,
    antibot_mode="combined",
    headless=False  # показать браузер
)
result = converter.get_cleaned_content_dict({"link": "https://cloudflare-protected.com"})
"""
