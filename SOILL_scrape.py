"""
SOILL Catalogue of Best Practices (T4.4) — web scraper
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Sequentially crawls each seed URL in urls_to_scrape.txt. Crawling stays on the
same domain and, for nested seeds (e.g. /projects/gov4all), only under that path
prefix — it does not walk up to parent site sections. Domain-root seeds crawl the
whole site. Articles are extracted from HTML blocks matching CONTENT_CLASSES.

Usage:
    python3 SOILL_scrape.py

Configuration: .env (MONGO_*, MIN_DELAY, REQUEST_TIMEOUT, MAX_PAGES_PER_SITE)
"""

import logging
import os
import random
from collections import deque
from datetime import datetime, timezone
from time import sleep
from typing import Any, Deque, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag
from pymongo import MongoClient

from config import (
    MAX_PAGES_PER_SITE,
    MIN_DELAY,
    MONGO_COLLECTION,
    MONGO_DB,
    MONGO_URI,
    REQUEST_TIMEOUT,
)

USER_AGENT = 'SOILLBot/1.0 (+research; SOILL T4.4 Catalogue of Best Practices agent)'

# HTML class-name markers that identify an Article container
CONTENT_CLASSES = (
    'content', 'article', 'post', 'entry', 'story', 'news',
    'blog', 'feature', 'item', 'card', 'panel', 'block',
    'section', 'hero', 'intro', 'text', 'wrapper',
)

SKIP_EXTENSIONS = (
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.rar', '.jpg', '.jpeg', '.png', '.gif', '.svg',
    '.mp4', '.mp3', '.xml', '.json',
)

_robots_cache: Dict[str, Optional[RobotFileParser]] = {}


def setup_logging() -> logging.Logger:
    """Configure logging to file; console progress uses print()."""
    os.makedirs('logs', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/SOILL_scrape_{timestamp}.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file)],
    )
    log = logging.getLogger(__name__)
    log.info('Logging initialised. Log file: %s', log_file)
    return log


logger = setup_logging()


def progress(message: str) -> None:
    """Write crawl progress to the console."""
    print(message, flush=True)


def get_mongodb_client() -> MongoClient:
    """Connect to local MongoDB and verify the server is reachable."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    logger.info('Connected to MongoDB at %s', MONGO_URI)
    return client


def _element_text(element: Any) -> str:
    """Return normalised plain text from a BeautifulSoup node or string."""
    if element is None:
        return ''
    if isinstance(element, str):
        return element.strip()
    if isinstance(element, Tag):
        return element.get_text(separator=' ', strip=True)
    return str(element).strip()


def _matches_content_class(class_value: Any) -> bool:
    if not class_value:
        return False
    lower = str(class_value).lower()
    return any(marker in lower for marker in CONTENT_CLASSES)


def _normalise_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip('/') or '/'
    return f'{parsed.scheme}://{parsed.netloc}{path}'


def _seed_path_prefix(seed_url: str) -> str:
    """Path prefix for crawl scope; '/' means the entire site (domain root seed)."""
    path = urlparse(seed_url).path.rstrip('/') or '/'
    return path


def _url_under_seed_path(url: str, seed_path_prefix: str) -> bool:
    """
    True if url's path is the seed path or a descendant (nested under the seed).

    Example: seed https://example.com/projects/gov4all only allows paths under
    /projects/gov4all, not /projects or /.
    """
    path = urlparse(url).path.rstrip('/') or '/'
    prefix = seed_path_prefix.rstrip('/') or '/'
    if prefix == '/':
        return True
    return path == prefix or path.startswith(f'{prefix}/')


def get_robots_parser(url: str) -> Optional[RobotFileParser]:
    """Return a cached robots parser for the URL's domain."""
    parsed_url = urlparse(url)
    domain_key = f'{parsed_url.scheme}://{parsed_url.netloc}'

    if domain_key in _robots_cache:
        return _robots_cache[domain_key]

    robots_url = f'{domain_key}/robots.txt'
    try:
        response = requests.get(
            robots_url,
            headers={'User-Agent': USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        rp = RobotFileParser()
        rp.set_url(robots_url)
        # Normalise line endings — RobotFileParser.read() can mis-parse CRLF files
        lines = response.text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        rp.parse(lines)
        _robots_cache[domain_key] = rp
        return rp
    except Exception as exc:
        logger.warning('Could not read robots.txt for %s: %s', domain_key, exc)
        _robots_cache[domain_key] = None
        return None


def can_fetch(url: str, user_agent: str = USER_AGENT) -> bool:
    """Check robots.txt permission."""
    rp = get_robots_parser(url)
    if rp is None:
        logger.warning('No robots.txt for %s — proceeding with caution', url)
        return True
    allowed = rp.can_fetch(user_agent, url)
    if not allowed:
        logger.warning('Robots.txt disallows scraping: %s', url)
    return allowed


def load_seed_urls(filename: str = 'urls_to_scrape.txt') -> List[Dict[str, str]]:
    """Load seed URLs and project names from the configuration file."""
    seeds: List[Dict[str, str]] = []
    with open(filename, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = [part.strip() for part in line.split(',', 1)]
            url = parts[0]
            project_name = parts[1] if len(parts) > 1 else urlparse(url).netloc

            if url:
                seeds.append({'url': url, 'project_name': project_name})

    logger.info('Loaded %d seed URLs from %s', len(seeds), filename)
    return seeds


def find_article_containers(soup: BeautifulSoup) -> List[Tag]:
    """
    Find HTML elements that qualify as Article containers:
    - native <article> tags, or
    - elements whose class attribute contains a CONTENT_CLASSES marker.
    """
    containers: List[Tag] = []
    seen_ids: Set[int] = set()

    for element in soup.find_all('article'):
        element_id = id(element)
        if element_id not in seen_ids:
            seen_ids.add(element_id)
            containers.append(element)

    for tag_name in ('section', 'motion', 'div'):
        for element in soup.find_all(tag_name, class_=_matches_content_class):
            element_id = id(element)
            if element_id not in seen_ids:
                seen_ids.add(element_id)
                containers.append(element)

    # Prefer innermost containers when one wraps another
    leaf_containers: List[Tag] = []
    for container in containers:
        if any(
            other is not container and other in container.descendants
            for other in containers
        ):
            continue
        leaf_containers.append(container)

    return leaf_containers


def extract_articles(soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
    """Extract Article records from HTML matching CONTENT_CLASSES."""
    articles: List[Dict[str, Any]] = []
    containers = find_article_containers(soup)
    logger.info('Found %d article container(s) on %s', len(containers), page_url)

    for container in containers:
        try:
            title = None
            title_tag_name = None
            title_candidates = container.find_all(
                ['h1', 'h2', 'h3', 'h4', 'motion'],
                class_=lambda value: value and any(
                    marker in str(value).lower()
                    for marker in ('title', 'headline', 'heading', 'name', 'caption')
                ),
            )

            if title_candidates:
                title = _element_text(title_candidates[0])
                title_tag_name = title_candidates[0].name
            else:
                title_parts = []
                for heading in ('h1', 'h2', 'h3', 'h4'):
                    heading_elem = container.find(heading)
                    if heading_elem:
                        text = _element_text(heading_elem)
                        if text:
                            title_parts.append(text)
                            if title_tag_name is None:
                                title_tag_name = heading
                if title_parts:
                    title = ' - '.join(title_parts)

            description_parts: List[str] = []
            seen_text: Set[str] = set()
            content_candidates = container.find_all(
                ['p', 'motion', 'div'],
                class_=lambda value: value and any(
                    marker in str(value).lower()
                    for marker in (
                        'description', 'summary', 'excerpt', 'content', 'text',
                        'body', 'copy', 'details', 'info', 'paragraph',
                    )
                ),
            )

            for content in content_candidates:
                text = _element_text(content)
                if len(text) > 25 and text not in seen_text:
                    description_parts.append(text)
                    seen_text.add(text)

            if not description_parts:
                for paragraph in container.find_all('p'):
                    text = _element_text(paragraph)
                    if len(text) > 50 and text not in seen_text:
                        description_parts.append(text)
                        seen_text.add(text)

            if not title or not description_parts:
                continue

            description = '\n\n'.join(description_parts)
            article_url = page_url

            canonical = soup.find('link', rel='canonical')
            if canonical and canonical.get('href'):
                article_url = urljoin(page_url, canonical['href'])

            link = container.find('a', href=True)
            if link and link.get('href'):
                article_url = urljoin(page_url, link['href'])

            articles.append({
                'title': title,
                'description': description,
                'heading_level': title_tag_name,
                'url': article_url,
                'scrape_date': datetime.now(timezone.utc),
                'content_type': 'article',
            })
        except Exception as exc:
            logger.error('Error processing article container on %s: %s', page_url, exc)

    return articles


def discover_links(
    soup: BeautifulSoup,
    page_url: str,
    site_domain: str,
    seed_path_prefix: str,
) -> List[str]:
    """Return same-domain HTML links under the seed path prefix."""
    links: List[str] = []

    for anchor in soup.find_all('a', href=True):
        try:
            href = anchor['href'].strip()
            if href.startswith(('javascript:', 'mailto:', 'tel:', 'fax:', '#')):
                continue

            absolute = urljoin(page_url, href)
            parsed = urlparse(absolute)

            if parsed.scheme not in ('http', 'https'):
                continue
            if parsed.netloc != site_domain:
                continue
            if any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
                continue

            normalised = _normalise_url(absolute)
            if not _url_under_seed_path(normalised, seed_path_prefix):
                continue

            links.append(normalised)
        except Exception as exc:
            logger.debug('Error processing link on %s: %s', page_url, exc)

    return list(dict.fromkeys(links))


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL and return parsed HTML, or None on failure."""
    if not can_fetch(url):
        progress(f'    Skipped (robots.txt): {url}')
        return None

    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.5',
        'Connection': 'keep-alive',
    }

    sleep(MIN_DELAY + random.random() * 2)

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        progress(f'    Error fetching: {url} ({exc})')
        logger.error('Error fetching %s: %s', url, exc)
        return None

    content_type = response.headers.get('content-type', '').lower()
    if 'text/html' not in content_type:
        progress(f'    Skipped (not HTML): {url}')
        return None

    return BeautifulSoup(response.text, 'html.parser')


def crawl_website(
    seed: Dict[str, str],
    site_index: int,
    site_total: int,
    collection: Any,
) -> Dict[str, int]:
    """
    Crawl an entire same-domain website, extracting Articles from each page.

    Returns counts: pages_crawled, articles_inserted, articles_skipped_duplicate.
    """
    seed_url = seed['url']
    project_name = seed['project_name']
    site_domain = urlparse(seed_url).netloc
    start_url = _normalise_url(seed_url)
    seed_path_prefix = _seed_path_prefix(seed_url)

    visited: Set[str] = set()
    queue: Deque[str] = deque([start_url])
    seen_articles: Set[str] = set()

    pages_crawled = 0
    articles_inserted = 0
    articles_skipped = 0

    limit_label = (
        str(MAX_PAGES_PER_SITE) if MAX_PAGES_PER_SITE > 0 else 'unlimited'
    )
    progress('')
    progress('=' * 72)
    progress(f'Website {site_index}/{site_total}: {project_name}')
    progress(f'  Seed URL : {seed_url}')
    progress(f'  Domain   : {site_domain}')
    scope_label = (
        'entire site (domain root seed)'
        if seed_path_prefix == '/'
        else f'path prefix {seed_path_prefix}/'
    )
    progress(f'  Scope    : {scope_label}')
    progress(f'  Page cap : {limit_label}')
    progress('=' * 72)

    while queue:
        if MAX_PAGES_PER_SITE > 0 and pages_crawled >= MAX_PAGES_PER_SITE:
            progress(
                f'  Reached MAX_PAGES_PER_SITE ({MAX_PAGES_PER_SITE}) — stopping crawl'
            )
            break

        url = queue.popleft()
        if url in visited:
            continue

        queued_remaining = len(queue)
        progress(
            f'  Fetching | queue {queued_remaining} | {url}'
        )

        soup = fetch_page(url)
        if soup is None:
            continue

        visited.add(url)
        pages_crawled += 1
        progress(
            f'  Page {pages_crawled} | queue {queued_remaining} | {url}'
        )

        articles = extract_articles(soup, url)
        if articles:
            progress(f'    → {len(articles)} article(s) found')
        else:
            progress('    → no articles on this page')

        for article in articles:
            dedupe_key = f"{article['url']}|{article['title']}"
            if dedupe_key in seen_articles:
                articles_skipped += 1
                continue
            seen_articles.add(dedupe_key)

            article.update({
                'source': url,
                'seed_url': seed_url,
                'project_name': project_name,
                'source_domain': site_domain,
            })
            try:
                result = collection.insert_one(article)
                articles_inserted += 1
                progress(f'      Saved: {article["title"][:70]}')
                logger.info(
                    'Inserted %s for %s: %s',
                    result.inserted_id,
                    project_name,
                    article['title'][:80],
                )
            except Exception as exc:
                logger.error('Error inserting article from %s: %s', url, exc)

        new_links = discover_links(soup, url, site_domain, seed_path_prefix)
        added = 0
        for link in new_links:
            if link not in visited and link not in queue:
                queue.append(link)
                added += 1
        if added:
            progress(f'    → {added} new link(s) queued')

    progress('')
    progress(
        f'  Finished {project_name}: {pages_crawled} page(s) crawled, '
        f'{articles_inserted} article(s) saved'
        + (f', {articles_skipped} duplicate(s) skipped' if articles_skipped else '')
    )

    return {
        'pages_crawled': pages_crawled,
        'articles_inserted': articles_inserted,
        'articles_skipped': articles_skipped,
    }


def scrape_soill_catalogue() -> None:
    """Sequentially crawl each website in urls_to_scrape.txt."""
    try:
        seeds = load_seed_urls()
    except FileNotFoundError:
        progress('ERROR: urls_to_scrape.txt not found')
        return
    except Exception as exc:
        progress(f'ERROR: Failed to load URLs: {exc}')
        return

    if not seeds:
        progress('ERROR: No URLs found in urls_to_scrape.txt')
        return

    try:
        client = get_mongodb_client()
        collection = client[MONGO_DB][MONGO_COLLECTION]
    except Exception as exc:
        progress(f'ERROR: Failed to connect to MongoDB: {exc}')
        progress(
            'Ensure Docker MongoDB is running on port 27017 '
            '(see .env MONGO_URI)'
        )
        return

    progress(f'Starting SOILL scrape — {len(seeds)} website(s) to process')
    progress(f'MongoDB: {MONGO_DB}.{MONGO_COLLECTION}')

    total_pages = 0
    total_articles = 0
    site_total = len(seeds)

    try:
        for index, seed in enumerate(seeds, start=1):
            stats = crawl_website(seed, index, site_total, collection)
            total_pages += stats['pages_crawled']
            total_articles += stats['articles_inserted']

        progress('')
        progress('=' * 72)
        progress('Scrape complete')
        progress(f'  Websites processed : {site_total}')
        progress(f'  Pages crawled      : {total_pages}')
        progress(f'  Articles saved     : {total_articles}')
        progress(f'  Total in collection: {collection.count_documents({})}')
        progress('=' * 72)

        logger.info(
            'Run complete: %d sites, %d pages, %d articles inserted',
            site_total,
            total_pages,
            total_articles,
        )
    except Exception as exc:
        progress(f'ERROR during scrape: {exc}')
        logger.error('Error during scrape: %s', exc)
    finally:
        client.close()
        logger.info('MongoDB connection closed')


if __name__ == '__main__':
    scrape_soill_catalogue()
