#!/usr/bin/env python3
"""
Web scraper to convert GitBook documentation pages to markdown files.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import html2text
from pathlib import Path

class GitBookScraper:
    def __init__(self, output_dir='/srv/shared/Models/hyperLiquidAgent/test/runs/dataset'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Configure html2text converter
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.body_width = 0  # Don't wrap lines
        self.h.unicode_snob = True
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def clean_filename(self, url):
        """Generate a clean filename from URL"""
        parsed = urlparse(url)
        path = parsed.path
        
        # Remove .md extension if present for processing
        if path.endswith('.md'):
            path = path[:-3]
        
        # Remove leading slash and replace slashes with underscores
        filename = path.lstrip('/').replace('/', '_')
        
        # Clean up the filename
        filename = re.sub(r'[^\w\-_.]', '_', filename)
        filename = re.sub(r'_+', '_', filename)  # Multiple underscores to single
        filename = filename.strip('_')
        
        # Handle root case
        if not filename:
            filename = 'index'
            
        return filename + '.md'
    
    def get_original_url(self, url_with_md):
        """Convert .md URL back to original GitBook URL"""
        if url_with_md.endswith('.md'):
            return url_with_md[:-3]
        return url_with_md
    
    def scrape_page(self, url):
        """Scrape a single page and return markdown content"""
        original_url = self.get_original_url(url)
        
        try:
            print(f"Fetching: {original_url}")
            response = self.session.get(original_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to find the main content area
            content_selectors = [
                'main',
                '[data-testid="content"]',
                '.content',
                'article',
                '.markdown-body',
                '#content'
            ]
            
            content = None
            for selector in content_selectors:
                content = soup.select_one(selector)
                if content:
                    break
            
            # If no specific content area found, use body but remove nav/header/footer
            if not content:
                content = soup.find('body')
                if content:
                    # Remove navigation, headers, footers, and other non-content elements
                    for elem in content.find_all(['nav', 'header', 'footer', 'aside']):
                        elem.decompose()
                    for elem in content.find_all(attrs={'class': re.compile(r'nav|header|footer|sidebar|menu', re.I)}):
                        elem.decompose()
            
            if not content:
                print(f"Warning: No content found for {original_url}")
                return f"# {original_url}\n\nNo content could be extracted from this page."
            
            # Convert to markdown
            markdown = self.h.handle(str(content))
            
            # Clean up the markdown
            markdown = re.sub(r'\n\n\n+', '\n\n', markdown)  # Multiple newlines to double
            markdown = markdown.strip()
            
            # Add title if not present
            if not markdown.startswith('#'):
                title = soup.find('title')
                if title:
                    markdown = f"# {title.get_text().strip()}\n\n{markdown}"
                else:
                    markdown = f"# {original_url}\n\n{markdown}"
            
            return markdown
            
        except requests.RequestException as e:
            error_msg = f"# Error fetching {original_url}\n\nError: {str(e)}"
            print(f"Error fetching {original_url}: {e}")
            return error_msg
        except Exception as e:
            error_msg = f"# Error processing {original_url}\n\nError: {str(e)}"
            print(f"Error processing {original_url}: {e}")
            return error_msg
    
    def scrape_urls(self, urls_file):
        """Scrape all URLs from the file"""
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        print(f"Found {len(urls)} URLs to scrape")
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Processing: {url}")
            
            # Generate filename
            filename = self.clean_filename(url)
            filepath = self.output_dir / filename
            
            # Skip if file already exists
            if filepath.exists():
                print(f"Skipping (already exists): {filename}")
                continue
            
            # Scrape the page
            markdown_content = self.scrape_page(url)
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            print(f"Saved: {filename}")
            
            # Be nice to the server
            time.sleep(1)
        
        print(f"\nScraping complete! Files saved to {self.output_dir}")

def main():
    scraper = GitBookScraper()
    scraper.scrape_urls('sites.txt')

if __name__ == '__main__':
    main()
