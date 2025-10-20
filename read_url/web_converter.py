#!/usr/bin/env python3

import json
import sys
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
    )
    try:
        from crawl4ai import UndetectedAdapter
    except ImportError:
        UndetectedAdapter = None
    from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

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
            logger.info(f"Loading URL using antibot ({self.antibot_mode}): {url}")

            browser_config = BrowserConfig(
                headless=self.headless,
                verbose=True
            )

            if self.antibot_mode == "stealth":
                browser_config.enable_stealth = True
                crawler_strategy = None

            elif self.antibot_mode == "undetected" and UndetectedAdapter:
                adapter = UndetectedAdapter()
                crawler_strategy = AsyncPlaywrightCrawlerStrategy(
                    browser_config=browser_config,
                    browser_adapter=adapter
                )

            elif self.antibot_mode == "combined" and UndetectedAdapter:
                browser_config.enable_stealth = True
                adapter = UndetectedAdapter()
                crawler_strategy = AsyncPlaywrightCrawlerStrategy(
                    browser_config=browser_config,
                    browser_adapter=adapter
                )
            else:
                logger.warning(f"Antibot mode {self.antibot_mode} is unavailable. Stealth is being used.")
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
                logger.error(f"✗ Error during loading {url}: {result.error_message if result else 'Unknown'}")
                return None

        except Exception as e:
            logger.error(f"Error during loading using antibot {url}: {e}")
            return None

    def fetch_url(self, url: str) -> Optional[str]:
        try:
            logger.info(f"Downloading URL (requests): {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error during loading {url}: {e}")
            return None

    def extract_content(self, html: str, url: str = None) -> Dict[str, str]:
        try:
            doc = Document(html)

            title = doc.title()
            content_html = doc.summary()

            if not content_html or len(content_html.strip()) < 100:
                logger.warning("Readability returned empty content, let's try the fallback method")
                return self._extract_content_fallback(html, url, title)

            soup = BeautifulSoup(content_html, 'html.parser')

            for tag in soup.find_all([
                'script', 'style', 'nav', 'aside', 'footer',
                'header', 'figcaption', 'iframe', 'frame',
                'object', 'embed', 'applet', 'noscript'
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

            if not markdown or len(markdown.strip()) < 50:
                logger.warning("Markdown turned out to be too short, let's try the fallback method")
                return self._extract_content_fallback(html, url, title)

            return {
                'title': title.strip() if title else '',
                'content': markdown.strip()
            }

        except Exception as e:
            logger.error(f"Error retrieving content: {e}")
            try:
                return self._extract_content_fallback(html, url, None)
            except:
                return {'title': '', 'content': ''}

    def _extract_content_fallback(self, html: str, url: str = None, title: str = None) -> Dict[str, str]:
        logger.info("Using the fallback method to retrieve content")

        soup = BeautifulSoup(html, 'html.parser')

        if not title:
            title_tag = soup.find('title')
            title = title_tag.get_text() if title_tag else ''

            if not title:
                h1_tag = soup.find('h1')
                title = h1_tag.get_text() if h1_tag else ''

        for tag in soup.find_all([
            'script', 'style', 'nav', 'aside', 'footer',
            'header', 'iframe', 'frame', 'noscript',
            'object', 'embed', 'applet'
        ]):
            tag.decompose()

        main_content = None

        for selector in ['main', 'article', '[role="main"]', '.main-content', '.article-content', '.post-content']:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if not main_content:
            main_content = soup.find('body')

        if not main_content:
            main_content = soup

        for tag in main_content.find_all(True):
            tag.attrs = {k: v for k, v in tag.attrs.items()
                       if k in ['href', 'src', 'alt', 'title']}

        if url:
            for link in main_content.find_all('a', href=True):
                link['href'] = urljoin(url, link['href'])
            for img in main_content.find_all('img', src=True):
                img['src'] = urljoin(url, img['src'])

        markdown = self.h2t.handle(str(main_content))
        markdown = self._clean_markdown(markdown)

        return {
            'title': title.strip() if title else '',
            'content': markdown.strip()
        }

    def _clean_markdown(self, markdown: str) -> str:
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        markdown = re.sub(r'\[\]\(\)', '', markdown)

        lines = [line.rstrip() for line in markdown.split('\n')]
        markdown = '\n'.join(lines)

        return markdown.strip()

    async def process_single_url_async(self, url_data: Dict) -> Optional[Dict]:
        url = url_data.get('link')
        if not url:
            logger.warning("URL missing in data")
            return None

        url = str(url)

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
            logger.warning("URL missing in data")
            return None

        url = str(url)

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

    async def get_cleaned_content_dict_async(self, url_data: Union[Dict, List[Dict]]) -> Union[Dict, List[Dict]]:
        if self.use_antibot:
            if isinstance(url_data, list):
                return await self.process_urls_async(url_data)
            else:
                return await self.process_single_url_async(url_data)
        else:
            loop = asyncio.get_event_loop()
            if isinstance(url_data, list):
                return await loop.run_in_executor(None, self.process_urls, url_data)
            else:
                return await loop.run_in_executor(None, self.process_single_url, url_data)

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
