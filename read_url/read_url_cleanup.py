#!/usr/bin/env python3

import json
import sys
import argparse
import re
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse

import requests
from readability import Document
from bs4 import BeautifulSoup
import html2text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebToMarkdownConverter:
    def __init__(self, delay: float = 1.0, timeout: int = 30):
        self.delay = delay
        self.timeout = timeout
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

    def fetch_url(self, url: str) -> Optional[str]:
        try:
            logger.info(f"Downloading URL: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to load {url}: {e}")
            return None

    def extract_content(self, html: str, url: str = None) -> Dict[str, str]:
        try:
            doc = Document(html)

            title = doc.title()
            content_html = doc.summary()

            soup = BeautifulSoup(content_html, 'html.parser')

            for tag in soup.find_all(['script', 'style', 'nav', 'aside', 'footer', 'header', 'figcaption']):
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

    def process_single_url(self, url_data: Dict) -> Optional[Dict]:
        url = url_data.get('link')
        if not url:
            logger.warning("URL missing in data")
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

            logger.info(f"Resulst saved to {output_file}")

        except Exception as e:
            logger.error(f"Error when saving results: {e}")


def main():
    parser = argparse.ArgumentParser(description='Web page converter to clean content')
    parser.add_argument('data', help='JSON string with data for processing')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests')
    parser.add_argument('--output', type=str, help='File for saving results')
    parser.add_argument('--print-json', action='store_true', help='Output the result in JSON format')

    args = parser.parse_args()

    try:
        input_data = json.loads(args.data)

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}", file=sys.stderr)
        print("Example: python3 script.py '{\"title\": \"Test\", \"link\": \"https://example.com\"}'", file=sys.stderr)
        sys.exit(1)

    converter = WebToMarkdownConverter(delay=args.delay)

    try:
        results = converter.get_cleaned_content_dict(input_data)

        if results:
            if args.print_json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                if isinstance(results, list):
                    print(f"{len(results)} pages processed")
                    for i, result in enumerate(results):
                        print(f"{i+1}. {result['title'][:100]}... ({result['word_count']} words)")
                else:
                    print(f"Article processed: {results['title'][:100]}... ({results['word_count']} words)")

            if args.output:
                converter.save_results(results, args.output)

        else:
            print("No articles could be processed.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


# Example of use in code:
"""
from web_converter import WebToMarkdownConverter

# Create a converter
converter = WebToMarkdownConverter()

# Sample data
url_data = {
    "title": "Example Article",
    "link": "https://example.com/article",
    "creator": "John Doe",
    "pubDate": "2024-01-01",
    "categories": ['tech', "ai"]
}

# Get cleaned content
cleaned_result = converter.get_cleaned_content_dict(url_data)

# The result will contain all the necessary fields:
# cleaned_result['content'] - cleaned content in markdown
# cleaned_result['title'] - title
# cleaned_result['creator'] - author
# and all other fields...
"""
