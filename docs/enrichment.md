# Enrichment & Web Research

mneia includes two agents for enhancing your knowledge with web data: the **EnrichmentAgent** (automatic, background) and the **WebResearchAgent** (on-demand, deep research).

## EnrichmentAgent

Automatically enhances sparse entities in your knowledge graph by searching the web for additional context.

### How It Works

1. Periodically scans the knowledge graph for entities with missing or short descriptions
2. For each sparse entity, performs a DuckDuckGo Instant Answer API search
3. When `enrichment_scrape_enabled` is true, also:
   - Extracts URLs from search results (AbstractURL and RelatedTopics)
   - Scrapes each URL using the shared web scraper
   - Feeds the scraped content to the LLM for richer context
4. The LLM extracts a concise description, relevant URL, and tags
5. Entity properties are updated in the knowledge graph

### Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `enrichment_scrape_enabled` | `false` | Enable web scraping for richer context |
| `enrichment_max_scrape_pages` | `5` | Max pages to scrape per cycle |
| `enrichment_scrape_delay_seconds` | `2.0` | Delay between requests (rate limiting) |

### Running

The enrichment agent runs automatically as part of the daemon:

```bash
mneia start
```

It runs on a 5-minute cycle, enriching up to 5 entities per cycle.

## WebResearchAgent

A standalone agent for deep topic research. Given a topic, it searches the web, scrapes relevant pages, and synthesizes a structured summary.

### How It Works

1. Searches DuckDuckGo for URLs related to the topic
2. Scrapes the top pages (up to `enrichment_max_scrape_pages`)
3. Sends scraped content to the LLM with a structured prompt
4. The LLM generates a research summary with:
   - Overview (2-3 sentences)
   - Key findings (bullet points)
   - Notable details
   - Sources used
5. The summary is stored as a `RawDocument` with `source="web-research"`

If the LLM fails during synthesis, the raw scraped content is concatenated as a fallback.

### Use Cases

- Deep-dive into a topic mentioned in your knowledge graph
- Background research on entities that the enrichment agent found
- On-demand research triggered by the AutonomousAgent

## Web Scraper

Both agents share a common web scraping utility (`mneia.connectors.web_scraper`):

1. **Primary**: Uses `crawl4ai` `AsyncWebCrawler` for JavaScript-rendered pages
2. **Fallback**: If crawl4ai is not installed, uses `httpx` + `html.parser` for basic HTML scraping
3. Content is cleaned and truncated to `max_content_length` (default: 10000 chars)

The Chrome History connector also uses this scraper when `scrape_content` is enabled.

## Privacy

- Web searches use DuckDuckGo's Instant Answer API (no tracking)
- Only entity names and topics are sent as search queries
- All enrichment data is stored locally in your knowledge graph
- Rate limiting prevents excessive requests
- Web scraping is opt-in and configurable
