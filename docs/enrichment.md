# Enrichment Agent

The Enrichment Agent enhances your knowledge graph by searching the web for additional context about entities (people, companies, topics) that have sparse descriptions.

## How It Works

1. The agent periodically scans the knowledge graph for entities with missing or short descriptions
2. For each sparse entity, it performs a web search (via DuckDuckGo Instant Answer API)
3. Search results are processed by the LLM to extract:
   - A concise description (1-2 sentences)
   - A relevant URL
   - Up to 5 tags
4. The entity's properties are updated in the knowledge graph

## Running the Agent

The enrichment agent runs automatically as part of the daemon when started:

```bash
mneia start
```

It runs on a 5-minute cycle, enriching up to 5 entities per cycle to avoid rate limiting.

## Configuration

The enrichment agent uses the same LLM configuration as the rest of mneia. No additional configuration is needed.

## Privacy

- Web searches are performed via DuckDuckGo's Instant Answer API (no tracking)
- Only entity names and types are sent as search queries
- All enrichment data is stored locally in your knowledge graph
- No personal data is sent to external services beyond the search query
