#!/usr/bin/env python3

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from deduplicator import ArticleDeduplicator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

deduplicator_instance = None

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

class ArticleRequest(BaseModel):
    articles: List[Dict] = Field(..., description="List of articles for deduplication")
    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Similarity threshold (0.0 - 1.0)"
    )

class ArticleResponse(BaseModel):
    unique_articles: List[Dict] = Field(..., description="List of unique articles")
    removed_count: int = Field(..., description="Number of duplicates removed")
    original_count: int = Field(..., description="Original number of articles")
    processing_time_seconds: float = Field(..., description="Processing time in seconds")

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class ErrorResponse(BaseModel):
    error: str
    detail: str

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
async def deduplicate_articles(request: ArticleRequest):
    global deduplicator_instance

    if deduplicator_instance is None:
        raise HTTPException(
            status_code=503,
            detail="The deduplication service has not been initialized."
        )

    if not request.articles:
        return ArticleResponse(
            unique_articles=[],
            removed_count=0,
            original_count=0,
            processing_time_seconds=0.0
        )

    try:
        import time
        start_time = time.time()

        if abs(request.similarity_threshold - deduplicator_instance.similarity_threshold) > 1e-6:
            temp_deduplicator = ArticleDeduplicator(
                similarity_threshold=request.similarity_threshold
            )
            temp_deduplicator.sentence_model = deduplicator_instance.sentence_model
            unique_articles = temp_deduplicator.deduplicate_articles(request.articles)
        else:
            unique_articles = deduplicator_instance.deduplicate_articles(request.articles)

        processing_time = time.time() - start_time

        return ArticleResponse(
            unique_articles=unique_articles,
            removed_count=len(request.articles) - len(unique_articles),
            original_count=len(request.articles),
            processing_time_seconds=round(processing_time, 3)
        )

    except Exception as e:
        logger.error(f"Error during deduplication: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error during article processing: {str(e)}"
        )

@app.get("/", tags=["Info"])
async def root():
    return {
        "service": "Article Deduplicator API",
        "version": "1.0.0",
        "description": "API for deduplicating news articles",
        "endpoints": {
            "POST /deduplicate": "Article deduplication",
            "GET /health": "Service status check",
            "GET /docs": "Swagger documetation"
        }
    }

@app.post("/test", response_model=ArticleResponse, tags=["Test"])
async def test_deduplication():
    test_articles = [
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

    request = ArticleRequest(articles=test_articles, similarity_threshold=0.80)
    return await deduplicate_articles(request)

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
