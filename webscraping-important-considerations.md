# Web Scraping - Important Considerations

**SOILL Catalogue of Best Practices, T4.4**

**Author: Prof. S. Hallett, Cranfield University**

## Ethics and Legality

### Core Principles

- Check for a website's 'robots.txt' file before scraping
- Review the terms of service thoroughly
- Include appropriate delays between requests
- Identify the scraper with a clear user-agent
- Respect site-specific crawling rules
- Limit crawl depth and total URLs processed

### Implementation in `SOILL_scrape.py`

- Minimum delay: `MIN_DELAY` seconds between requests (plus small random jitter; see `.env`)
- User-agent: `SOILLBot/1.0 (+research; SOILL T4.4 Catalogue of Best Practices agent)`
- `robots.txt` checked per domain before each fetch
- Same-domain crawl only; nested seeds are limited to URLs under the seed path prefix
- Optional cap: `MAX_PAGES_PER_SITE` (`0` = no cap per seed)
- Articles only: native `<article>` or blocks matching `CONTENT_CLASSES` in the scraper

## Best Practices

### Error Handling

- Implement comprehensive try-catch blocks
- Log all errors and warnings
- Handle network timeouts gracefully
- Validate content types before processing
- Skip non-HTML content

### Rate Limiting

- Add random delays between requests
- Implement exponential backoff for failures
- Respect site-specific rate limits
- Monitor request frequency

### Data Storage

- Store data systematically in MongoDB
- Include metadata (scrape_date, source, depth)
- Implement proper error handling for database operations
- Maintain data integrity and consistency

### Logging

- Maintain detailed logs of all operations
- Log to both file and console
- Include timestamps and severity levels
- Track progress and statistics

## Alternative Approaches

### APIs and Feeds

- Consider using official APIs when available
- Look for RSS feeds as they are easier to parse
- Check for JSON/XML endpoints
- Evaluate API rate limits and costs

### Web sources

- Research available LL LH web portals
- In forst instance restrict to Mission Soil LL/LH
- Look for curated descriptions
- Evaluate materials for freshness and quality

## Technical Implementation

### Selector Definition

- Modify selectors based on target website structure
- Use multiple fallback selectors
- Consider common content containers:
  - article, section, div
  - Classes: content, article, post, entry, story, news
  - Roles: main, article, contentinfo
- Handle various heading levels (h1, h2, h3)

### Content Extraction

- Extract titles and descriptions
- Handle various HTML structures
- Implement content validation
- Clean and normalise extracted text

### URL Management

- Convert relative URLs to absolute (`urljoin`)
- Normalise paths (trailing slash) for visit tracking
- Same-domain links only; nested seeds cannot crawl above their path prefix
- Skip non-HTML and common binary extensions (PDF, images, archives, etc.)
- In-run duplicate detection by `url|title` (re-scraping the same seed can still add MongoDB duplicates)

## Configuration

### External Configuration

- Use urls_to_scrape.txt for source URLs
- Format: CSV with URL and Description columns
- Support comments and empty lines
- Enable easy source management

### Database Configuration

- MongoDB connection settings
- Collection structure
- Index management
- Error handling

## Monitoring and Maintenance

### Performance Tracking

- Monitor scraping speed
- Track success rates
- Log error patterns
- Measure data quality

### Regular Updates

- Review and update source URLs
- Adjust rate limits as needed
- Update selectors for site changes
- Maintain documentation
