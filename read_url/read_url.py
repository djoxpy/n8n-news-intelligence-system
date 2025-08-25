#!/usr/bin/env python3

import json
import sys
import argparse
import re
import time
import logging
from datetime import datetime
from pathlib import Path
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
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.ignore_emphasis = False
        self.h2t.body_width = 0
        self.h2t.unicode_snob = True
        self.h2t.decode_errors = 'ignore'

    def fetch_url(self, url: str) -> Optional[str]:
        try:
            logger.info(f"Download URL: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error loading {url}: {e}")
            return None

    def extract_content(self, html: str, url: str = None) -> Dict[str, str]:
        try:
            doc = Document(html)

            title = doc.title()
            content_html = doc.summary()

            soup = BeautifulSoup(content_html, 'html.parser')

            for tag in soup.find_all(['script', 'style', 'nav', 'aside', 'footer', 'header']):
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

    def create_structured_output(self, url_data: Dict, extracted: Dict[str, str], url: str) -> Dict:
        return {
            'metadata': {
                'source_url': url,
                'original_title': url_data.get('title', ''),
                'extracted_title': extracted['title'],
                'creator': url_data.get('creator', ''),
                'publication_date': url_data.get('pubDate', ''),
                'categories': url_data.get('categories', []),
                'content_snippet': url_data.get('contentSnippet', ''),
                'processed_at': datetime.now().isoformat(),
                'domain': urlparse(url).netloc
            },
            'content': {
                'markdown': extracted['content'],
                'word_count': len(extracted['content'].split()),
                'char_count': len(extracted['content'])
            }
        }

    def process_urls(self, url_list: List[Dict]) -> List[Dict]:
        results = []

        for i, url_data in enumerate(url_list):
            url = url_data.get('link')
            if not url:
                logger.warning(f"Skipping entry {i}: URL missing")
                continue

            logger.info(f"Processing {i+1}/{len(url_list)}: {url}")

            html = self.fetch_url(url)
            if not html:
                logger.warning(f"Failed to load {url}")
                continue

            extracted = self.extract_content(html, url)

            if not extracted['content']:
                logger.warning(f"Unable to retrieve content from {url}")
                continue

            result = self.create_structured_output(url_data, extracted, url)
            results.append(result)

            if i < len(url_list) - 1:
                time.sleep(self.delay)

        return results

    def save_results(self, results: List[Dict], output_file: str = None):
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"extracted_content_{timestamp}.json"

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            logger.info(f"Results saved to {output_file}")

        except Exception as e:
            logger.error(f"Error while saving results: {e}")

    def save_markdown_files(self, results: List[Dict], output_dir: str = "markdown_output"):
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        for i, result in enumerate(results):
            metadata = result['metadata']
            content = result['content']

            title = metadata.get('extracted_title') or metadata.get('original_title') or f"article_{i+1}"
            filename = re.sub(r'[^\w\s-]', '', title.replace(' ', '_'))[:50] + '.md'

            markdown_content = f"""# {metadata.get('extracted_title', 'No title')}

## Metadata
- **Source**: {metadata['source_url']}
- **Author**: {metadata.get('creator', 'Not specified')}
- **Publication date**: {metadata.get('publication_date', 'Not specified')}
- **Domain**: {metadata['domain']}
- **Categories**: {', '.join(metadata.get('categories', []))}
- **Processed at**: {metadata['processed_at']}
- **Word count**: {content['word_count']}

## Short description
{metadata.get('content_snippet', 'Description is missing')}

---

{content['markdown']}
"""

            file_path = output_path / filename
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                logger.info(f"File saved: {file_path}")
            except Exception as e:
                logger.error(f"Error while saving {file_path}: {e}")

    def print_markdown_results(self, results: List[Dict]):
        for i, result in enumerate(results):
            metadata = result['metadata']
            content = result['content']

            markdown_content = f"""# {metadata.get('extracted_title', 'No title')}

## Metadata
- **Source**: {metadata['source_url']}
- **Author**: {metadata.get('creator', 'Not specified')}
- **Publication date**: {metadata.get('publication_date', 'Not specified')}
- **Domain**: {metadata['domain']}
- **Categories**: {', '.join(metadata.get('categories', []))}
- **Processed at**: {metadata['processed_at']}
- **Word count**: {content['word_count']}

## Short description
{metadata.get('content_snippet', 'Description is missing')}

---

{content['markdown']}
"""

            print(markdown_content)

            if i < len(results) - 1:
                print("\n" + "="*80 + "\n")

            logger.info(f"Article displayed {i+1}: {metadata.get('extracted_title', f'article_{i+1}')}")

def main():
    parser = argparse.ArgumentParser(description='Web page converter to Markdown')
    parser.add_argument('data', help='JSON string with data for processing')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (default: 1.0)')

    args = parser.parse_args()

    try:
        sample_data = json.loads(args.data)

        if not isinstance(sample_data, list):
            sample_data = [sample_data]

    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}", file=sys.stderr)
        print("Example of correct format:", file=sys.stderr)
        print('python3 read_url.py \'[{"title": "Test", "link": "https://example.com"}]\'', file=sys.stderr)
        sys.exit(1)

    converter = WebToMarkdownConverter(delay=args.delay)

    try:
        results = converter.process_urls(sample_data)

        # converter.save_results(results)
        # converter.save_markdown_files(results)
        converter.print_markdown_results(results)

        print(f"{len(results)} pages processed", file=sys.stderr)

    except Exception as e:
        print(f"Error processing data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
