#!/usr/bin/env python3

import asyncio
import logging
import os
import json
from contextlib import asynccontextmanager
from typing import Dict, List, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from deduplicator import ArticleDeduplicator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

deduplicator_instance: Optional[ArticleDeduplicator] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global deduplicator_instance

    logger.info("Initialization of the deduplication service...")
    try:
        default_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.85'))
        deduplicator_instance = ArticleDeduplicator(similarity_threshold=default_threshold)
        logger.info("The deduplication service has been successfully initialized.")
    except Exception as e:
        logger.error(f"Error during service initialization: {e}")
        raise RuntimeError(f"Failed to initialize the deduplication service: {e}")

    yield

    logger.info("Termination of deduplication service...")
    deduplicator_instance = None

app = FastAPI(
    title="Article Deduplicator API",
    description="API for deduplicating news articles based on semantic analysis",
    version="1.0.0",
    lifespan=lifespan
)

class ArticleDataSource(BaseModel):
    data: List[Dict] = Field(..., description="List of articles in the source")

class ArticleResponse(BaseModel):
    unique_articles: List[Dict] = Field(..., description="List of unique articles")
    removed_count: int = Field(..., description="Number of duplicates removed")
    original_count: int = Field(..., description="Original number of articles")
    processing_time_seconds: float = Field(..., description="Processing time in seconds")

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

async def _parse_incoming_request(request: Request) -> Dict[str, Any]:
    try:
        outer = await request.json()
    except Exception as e:
        body_bytes = await request.body()
        raise HTTPException(status_code=422, detail=f"Invalid JSON body: {e}; raw_body={body_bytes!r}")

    if isinstance(outer, dict) and 'body' in outer and isinstance(outer['body'], str):
        inner_raw = outer['body']
        try:
            inner = json.loads(inner_raw)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid nested JSON in 'body': {e}")
        return inner

    return outer

def _extract_articles_and_threshold(parsed: Dict[str, Any], default_threshold: float) -> (List[Dict], float):
    threshold = default_threshold
    if isinstance(parsed, dict) and 'similarity_threshold' in parsed:
        try:
            threshold = float(parsed['similarity_threshold'])
        except Exception:
            threshold = default_threshold

    all_articles: List[Dict] = []

    if isinstance(parsed, dict):
        if 'sources' in parsed and isinstance(parsed['sources'], list):
            for src in parsed['sources']:
                if isinstance(src, dict) and src.get('data'):
                    if isinstance(src['data'], list):
                        all_articles.extend(src['data'])
        elif 'data' in parsed and isinstance(parsed['data'], list):
            all_articles.extend(parsed['data'])
        elif 'articles' in parsed and isinstance(parsed['articles'], list):
            all_articles.extend(parsed['articles'])
        else:
            if isinstance(parsed, list):
                all_articles.extend(parsed)

    return all_articles, threshold

def _deduplicate_with_threshold(articles: List[Dict], threshold: float) -> List[Dict]:
    global deduplicator_instance
    if deduplicator_instance is None:
        raise RuntimeError("The deduplication service has not been initialized.")

    if abs(threshold - deduplicator_instance.similarity_threshold) > 1e-6:
        temp = ArticleDeduplicator(similarity_threshold=threshold)
        temp.sentence_model = deduplicator_instance.sentence_model
        return temp.deduplicate_articles(articles)
    else:
        return deduplicator_instance.deduplicate_articles(articles)

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    global deduplicator_instance

    if deduplicator_instance is None:
        raise HTTPException(status_code=503, detail="The service is not ready")

    return HealthResponse(
        status="healthy",
        service="Article Deduplicator",
        version="1.0.0"
    )

@app.post("/deduplicate", response_model=ArticleResponse, tags=["Deduplication"])
async def deduplicate_articles(request: Request):
    global deduplicator_instance

    if deduplicator_instance is None:
        raise HTTPException(status_code=503, detail="The deduplication service has not been initialized")

    parsed = await _parse_incoming_request(request)
    all_articles, threshold = _extract_articles_and_threshold(parsed, deduplicator_instance.similarity_threshold)

    if not all_articles:
        return ArticleResponse(
            unique_articles=[],
            removed_count=0,
            original_count=0,
            processing_time_seconds=0.0
        )

    try:
        import time
        start_time = time.time()

        unique_articles = _deduplicate_with_threshold(all_articles, threshold)

        processing_time = time.time() - start_time

        return ArticleResponse(
            unique_articles=unique_articles,
            removed_count=len(all_articles) - len(unique_articles),
            original_count=len(all_articles),
            processing_time_seconds=round(processing_time, 3)
        )

    except Exception as e:
        logger.exception("Error during deduplication")
        raise HTTPException(status_code=500, detail=f"Error while processing articles: {e}")

@app.post("/deduplicate-legacy", response_model=ArticleResponse, tags=["Deduplication"])
async def deduplicate_articles_legacy(request: Request):
    return await deduplicate_articles(request)

@app.get("/", tags=["Info"])
async def root():
    return {
        "service": "Article Deduplicator API",
        "version": "1.0.0",
        "description": "API for deduplicating news articles",
        "endpoints": {
            "POST /deduplicate": "Article deduplication (new format and wrapped format)",
            "POST /deduplicate-legacy": "Article deduplication (old format)",
            "GET /health": "Service status check",
            "GET /docs": "Swagger documetation"
        }
    }

@app.post("/test", response_model=ArticleResponse, tags=["Test"])
async def test_deduplication():
    test_data = [
        {
            "data": [
                {
                    "creator": "Al Jazeera",
                    "title": "Somalia cuts UAE ties after Yemen separatist's illegal entry",
                    "link": "https://www.aljazeera.com/news/2026/1/13/somalia-cuts-uae-ties-yemen-separatist",
                    "pubDate": "Mon, 13 Jan 2026 14:49:46 +0000",
                    "author": "Faisal Ali",
                    "guid": "https://www.aljazeera.com/news/2026/1/13/somalia-cuts-uae-ties-yemen-separatist",
                    "categories": ["International News"],
                    "isoDate": "2026-01-13T14:49:46.000Z"
                },
                {
                    "creator": "Al Jazeera",
                    "title": "How will Trump's new 25% tariff impact Iran's trading partners?",
                    "link": "https://www.aljazeera.com/news/2026/1/13/trump-tariff-iran-trading",
                    "pubDate": "Mon, 13 Jan 2026 14:45:09 +0000",
                    "author": "Sarah Shamim",
                    "guid": "https://www.aljazeera.com/news/2026/1/13/trump-tariff-iran-trading",
                    "categories": ["Politics / Economy"],
                    "isoDate": "2026-01-13T14:45:09.000Z"
                }
            ]
        }
    ]

    wrapped = { "body": json.dumps({"data": test_data[0]["data"], "similarity_threshold": 0.80}) }

    class DummyRequest:
        def __init__(self, obj):
            self._obj = obj
        async def json(self):
            return self._obj
        async def body(self):
            return json.dumps(self._obj).encode()

    dummy_req = DummyRequest(wrapped)
    return await deduplicate_articles(Request(scope={"type": "http"})) if False else await deduplicate_articles(dummy_req)  # type: ignore

if __name__ == "__main__":
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    workers = int(os.getenv('WORKERS', '1'))

    logger.info(f"Starting server {host}:{port}")

    if workers > 1:
        uvicorn.run(
            "app:app",
            host=host,
            port=port,
            workers=workers,
            log_level="info"
        )
    else:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            reload=False
        )
