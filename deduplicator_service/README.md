# Article Deduplicator

A microservice for deduplicating news articles based on semantic analysis. Uses transformer models to create text embeddings and identify duplicates based on similarity.

## Description

The `deduplicator_service` provides a REST API for detecting and removing duplicate articles from news collections. It analyzes semantic similarity between articles and removes duplicates based on a configurable similarity threshold.

### Key Features

- **Semantic Analysis**: Uses `paraphrase-multilingual-MiniLM-L12-v2` model for creating embeddings
- **Flexible Similarity Thresholds**: Support for dynamic thresholds per request
- **High Performance**: Optimized comparison algorithm using cosine similarity
- **Multiple Format Support**: Compatibility with both new and legacy data formats
- **Docker Ready**: Dockerfile included for container deployment

## Technology Stack

- **FastAPI**: Modern web framework for Python
- **Sentence Transformers**: Text embedding generation
- **scikit-learn**: Cosine similarity computation
- **NumPy**: Numerical operations
- **Uvicorn**: ASGI server
- **Docker**: Container orchestration

## Usage

### Main Endpoint: `/deduplicate` (POST)

Removes duplicates from a collection of articles.

#### Request Format (New)

```json
{
  "data": [
    {
      "title": "Article Title",
      "link": "https://example.com/article",
      "creator": "Author Name",
      "pubDate": "Mon, 13 Jan 2026 14:49:46 +0000",
      "content": "Article content",
      "categories": ["News", "Technology"]
    }
  ],
  "similarity_threshold": 0.85
}
```

#### Request Format (Wrapped - Legacy Compatibility)

```json
{
  "body": "{\"data\": [...], \"similarity_threshold\": 0.85}"
}
```

#### Request Format (Multiple Sources)

```json
{
  "sources": [
    {
      "data": [...]
    },
    {
      "data": [...]
    }
  ],
  "similarity_threshold": 0.85
}
```

#### Response Format

```json
{
  "unique_articles": [
    {
      "title": "Article Title",
      "link": "https://example.com/article",
      "creator": "Author Name",
      ...
    }
  ],
  "removed_count": 5,
  "original_count": 15,
  "processing_time_seconds": 2.341
}
```

### Health Check: `/health` (GET)

Verifies the service is operational.

#### Response

```json
{
  "status": "healthy",
  "service": "Article Deduplicator",
  "version": "1.0.0"
}
```

### Service Information: `/` (GET)

Returns information about available endpoints.

#### Response

```json
{
  "service": "Article Deduplicator API",
  "version": "1.0.0",
  "description": "API for deduplicating news articles",
  "endpoints": {
    "POST /deduplicate": "Article deduplication (new format and wrapped format)",
    "POST /deduplicate-legacy": "Article deduplication (old format)",
    "GET /health": "Service status check",
    "GET /docs": "Swagger documentation"
  }
}
```

### Test Endpoint: `/test` (POST)

Executes deduplication with sample data for testing.

### Legacy Compatibility: `/deduplicate-legacy` (POST)

Alternative endpoint for backward compatibility with older integrations.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMILARITY_THRESHOLD` | `0.85` | Global similarity threshold for deduplication |
| `HOST` | `0.0.0.0` | IP address to listen on |
| `PORT` | `8000` | Service port |
| `WORKERS` | `1` | Number of Uvicorn worker processes |

## How It Works

1. **Initialization**: Load the sentence transformer model (`paraphrase-multilingual-MiniLM-L12-v2`)
2. **Embedding Generation**: Convert article titles and content to dense vectors
3. **Similarity Computation**: Calculate cosine similarity between all article pairs
4. **Deduplication**: Remove articles that exceed the similarity threshold with existing articles
5. **Response**: Return unique articles with processing metrics

## Performance

The service is optimized for processing large article collections:

- Models loaded once during initialization
- NumPy vectorized operations for speed
- Cosine similarity for fast comparison
- Multi-worker support for concurrent requests

Approximate processing times:
- 100 articles: ~0.5 seconds
- 1,000 articles: ~2-3 seconds
- 10,000 articles: ~20-30 seconds

Memory requirements: ~2GB RAM for model loading

## Typical Use Cases

### Integration with n8n Workflows

The service integrates seamlessly with n8n through HTTP nodes:

```
Fetch News → HTTP POST /deduplicate → Process Unique Articles → Save to DB
```

### Batch Processing

Process multiple news sources simultaneously:

```bash
curl -X POST "http://localhost:8000/deduplicate" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [
      {"data": [...]},  # Source 1
      {"data": [...]}   # Source 2
    ],
    "similarity_threshold": 0.80
  }'
```

### Python Client Example

```python
import requests

url = "http://localhost:8000/deduplicate"
payload = {
    "data": [
        {
            "title": "Breaking News: Stock Market Surge",
            "link": "https://example.com/1",
            "creator": "John Doe"
        },
        {
            "title": "Market Reaches New Heights",  # Similar to first
            "link": "https://example.com/2",
            "creator": "Jane Smith"
        }
    ],
    "similarity_threshold": 0.85
}

response = requests.post(url, json=payload)
result = response.json()

print(f"Unique articles: {len(result['unique_articles'])}")
print(f"Duplicates removed: {result['removed_count']}")
print(f"Processing time: {result['processing_time_seconds']}s")
```

### cURL Example

```bash
curl -X POST "http://localhost:8000/deduplicate" \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {
        "title": "AI Breakthrough in NLP",
        "link": "https://example.com/ai-news",
        "creator": "Tech Reporter",
        "pubDate": "2026-01-15T10:00:00Z"
      },
      {
        "title": "New AI Language Model Released",
        "link": "https://example.com/ai-news-2",
        "creator": "AI News Daily",
        "pubDate": "2026-01-15T11:00:00Z"
      }
    ],
    "similarity_threshold": 0.80
  }'
```

## Similarity Threshold Guidelines

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| 0.95+ | Very strict, removes only near-identical articles | Exact duplicate detection |
| 0.85-0.95 | Strict, removes clearly duplicate articles | Standard news deduplication |
| 0.70-0.85 | Moderate, removes similar articles | News summarization |
| 0.50-0.70 | Lenient, removes loosely related articles | Topic clustering |

## Troubleshooting

### Issue: Service starts but models fail to load

**Solution**: Ensure you have an active internet connection for the first model download. Models are cached locally afterward. Check logs with `docker logs deduplicator`.

### Issue: High memory usage

**Solution**: The service requires ~2GB RAM for model loading. Ensure your container/machine has sufficient resources. Consider using a smaller model if necessary.

### Issue: Deduplication not working correctly

**Solution**: Adjust the `similarity_threshold` parameter. Higher values (0.95+) are stricter, lower values (0.70-) are more lenient. Test with `/test` endpoint first.

### Issue: Slow processing for large datasets

**Solution**: Increase the number of workers with `WORKERS=4` environment variable. Split large requests into smaller batches. Consider using GPU-enabled deployment for faster embeddings.

### Issue: Out of memory errors

**Solution**:
- Reduce batch size (process fewer articles per request)
- Increase container/machine memory limits
- Enable swap memory (if using Docker)
- Use a machine with more available RAM

## Advanced Configuration

### Custom Similarity Threshold per Request

```json
{
  "data": [...],
  "similarity_threshold": 0.75
}
```

### Processing Multiple Sources

```json
{
  "sources": [
    {"data": [articles from source 1]},
    {"data": [articles from source 2]},
    {"data": [articles from source 3]}
  ],
  "similarity_threshold": 0.85
}
```

## License

Part of the `n8n-news-intelligence-system` project. Please refer to the main repository lic

## Support

For issues and questions:
- GitHub Issues: https://github.com/djoxpy/n8n-news-intelligence-system/issues
- Check existing documentation and examples
- Review logs for error messages

---
