

# Article Classifier

## Overview

The **Article Classifier** is a Zero-shot Classification service that automatically categorizes news articles as relevant or not relevant based on their titles and content snippets. Built with FastAPI and powered by Facebook's BART-large-MNLI transformer model, this service provides intelligent article classification without requiring labeled training data.

**Version:** 1.0.0

## Features

- **Zero-shot Classification**: Classify articles without training data using transformer-based models
- **Confidence Threshold**: Configurable confidence threshold (0.0-1.0, default: 0.60) for flexible filtering
- **Batch Processing**: Process multiple articles in a single API request
- **Comprehensive Statistics**: Get category distribution and article counts
- **Docker Support**: Containerized deployment for easy scaling
- **Health Monitoring**: Built-in health check endpoint
- **Automatic Model Loading**: Model loads on startup with error handling

## Technology Stack

| Component | Details |
|-----------|---------|
| Framework | FastAPI 0.104+ |
| Runtime | Python 3.10+ |
| ML Model | facebook/bart-large-mnli (Hugging Face Transformers) |
| Server | Uvicorn ASGI |
| Container | Docker with Python 3.10-slim |
| Port | 8020 (default) |

## API Endpoints

### 1. POST /classify
**Classify one or more articles**

#### Request Body
```json
{
  "articles": [
    {
      "title": "string - Article headline (required)",
      "contentSnippet": "string - Article summary (required)",
      "additionalField": "any - Extra fields are preserved (optional)"
    }
  ],
  "threshold": "float - Confidence threshold 0.0-1.0 (default: 0.60)"
}
```

#### Response
```json
{
  "articles": [
    {
      "title": "string",
      "contentSnippet": "string",
      "category": "string - 'relevant_politics', 'relevant_tech', or 'not_relevant'",
      "confidence": "float - Confidence score 0.0-1.0",
      "threshold_applied": "bool - Whether threshold was applied"
    }
  ],
  "total": "int - Total number of articles processed",
  "statistics": {
    "relevant_politics": "int - Count",
    "relevant_tech": "int - Count",
    "not_relevant": "int - Count"
  }
}
```

#### Example Request
```bash
curl -X POST "http://localhost:8020/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [
      {
        "title": "New AI Breakthrough in Machine Learning",
        "contentSnippet": "Researchers announce significant advances in transformer models"
      },
      {
        "title": "Celebrity News Update",
        "contentSnippet": "Latest gossip from Hollywood stars"
      }
    ],
    "threshold": 0.65
  }'
```

#### Example Response
```json
{
  "articles": [
    {
      "title": "New AI Breakthrough in Machine Learning",
      "contentSnippet": "Researchers announce significant advances in transformer models",
      "category": "relevant_tech",
      "confidence": 0.92,
      "threshold_applied": false
    },
    {
      "title": "Celebrity News Update",
      "contentSnippet": "Latest gossip from Hollywood stars",
      "category": "not_relevant",
      "confidence": 0.15,
      "threshold_applied": true
    }
  ],
  "total": 2,
  "statistics": {
    "relevant_politics": 0,
    "relevant_tech": 1,
    "not_relevant": 1
  }
}
```

### 2. GET /health
**Check API health and model status**

#### Response
```json
{
  "status": "healthy",
  "model_loaded": true
}
```

#### Example Request
```bash
curl http://localhost:8020/health
```

### 3. GET /
**Get API information and available endpoints**

#### Response
```json
{
  "name": "News Article Classifier API",
  "version": "1.0.0",
  "endpoints": {
    "POST /classify": "Classify articles",
    "GET /health": "Health check",
    "GET /docs": "Swagger documentation"
  }
}
```

## Configuration

### Environment Variables

Set these environment variables to customize behavior:

- `HF_HOME`: Hugging Face cache directory (default: `/app/.cache/huggingface`)
- `TRANSFORMERS_CACHE`: Transformer models cache (default: `/app/.cache/huggingface`)
- `HF_DATASETS_CACHE`: Datasets cache (default: `/app/.cache/huggingface/datasets`)

### Model Configuration

Edit `api.py` to customize:

```python
CONFIDENCE_THRESHOLD = 0.60  # Default confidence threshold
RELEVANT_CATEGORIES = ["relevant_politics", "relevant_tech"]  # Classification categories
MODEL_NAME = "facebook/bart-large-mnli"  # Hugging Face model
```

## How It Works

### Zero-Shot Classification

The classifier uses zero-shot classification, meaning it can categorize articles without any training data:

1. **Input Processing**: Combines article title and content snippet (max 250 chars)
2. **Model Inference**: Uses BART-large-MNLI to compute confidence scores for each category
3. **Threshold Application**: Applies confidence threshold to determine final category
4. **Response Generation**: Returns classification with confidence and statistics

### Classification Categories

- **relevant_politics**: Articles related to political news and events
- **relevant_tech**: Articles about technology and scientific developments
- **not_relevant**: Articles that don't match the above categories (confidence below threshold)

### Performance Considerations

- **Model Size**: BART-large-MNLI is ~1.2GB (downloads on first use)
- **Memory**: Requires ~2-3GB RAM for inference
- **Latency**: ~1-2 seconds per article on CPU, <100ms on GPU
- **Batch Processing**: More efficient with batch requests (10+ articles)
- **Caching**: Models cached in Docker to avoid re-downloads

## Error Handling

The API returns appropriate HTTP status codes:

| Status | Meaning |
|--------|---------|
| 200 | Successful classification |
| 400 | Invalid request format |
| 500 | Server error or model failure |
| 503 | Model not loaded |

### Common Errors

```json
{
  "detail": "Model not loaded"
}
```
**Solution**: Wait for API startup (model downloads on first run)

```json
{
  "detail": "validation error"
}
```
**Solution**: Check request format matches schema (title and contentSnippet required)

## Troubleshooting

### Model Download Issues
- Check internet connection
- Verify disk space (>2GB needed)
- Check HF_HOME directory permissions

### Memory Issues
- Reduce batch size
- Increase swap space
- Use GPU: `device=0` instead of `device=-1` in api.py

### Slow Performance
- Verify network latency for remote requests
- Use batch requests instead of single articles
- Monitor CPU/memory usage during classification

## Logging

The API logs all activities with INFO level by default. Enable DEBUG logging:

```python
logging.basicConfig(level=logging.DEBUG)
```
## License

This project is part of the n8n News Intelligence System. Please refer to the main repository license.

## Links

- **Repository**: https://github.com/djoxpy/n8n-news-intelligence-system
- **Hugging Face Model**: https://huggingface.co/facebook/bart-large-mnli
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Docker Docs**: https://docs.docker.com/
