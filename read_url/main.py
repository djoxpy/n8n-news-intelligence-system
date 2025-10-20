#!/usr/bin/env python3

import json
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, Field
import uvicorn

from web_converter import WebToMarkdownConverter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Web to Markdown Converter API",
    description="Microservice for converting web pages into clean markdown with anti-bot system support",
    version="1.0.0"
)

class UrlData(BaseModel):
    link: HttpUrl
    title: Optional[str] = ""
    creator: Optional[str] = ""
    pubDate: Optional[str] = ""
    contentSnippet: Optional[str] = ""
    guid: Optional[str] = ""
    categories: Optional[List[str]] = []
    isoDate: Optional[str] = ""

    class Config:
        json_schema_extra = {
            "example": {
                "link": "https://example.com/article",
                "title": "Example Article",
                "creator": "John Doe"
            }
        }

class ConvertRequest(BaseModel):
    data: Union[UrlData, List[UrlData]] = Field(..., description="One URL or a list of URLs for processing")
    delay: float = Field(1.0, ge=0, le=10, description="Delay between requests in seconds")
    timeout: int = Field(30, ge=5, le=120, description="Request timeout in seconds")
    use_antibot: bool = Field(False, description="Use anti-bot system bypass modes")
    antibot_mode: str = Field("stealth", description="Anti-bot mode: stealth, undetected, combined")
    headless: bool = Field(True, description="Run the browser in headless mode")

    class Config:
        json_schema_extra = {
            "example": {
                "data": {
                    "link": "https://example.com/article",
                    "title": "Example Article"
                },
                "delay": 1.0,
                "use_antibot": False,
                "antibot_mode": "stealth"
            }
        }

class ConvertResponse(BaseModel):
    success: bool
    data: Optional[Union[Dict, List[Dict]]] = None
    error: Optional[str] = None
    processed_count: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class HealthResponse(BaseModel):
    status: str
    version: str
    crawl4ai_available: bool
    timestamp: str


@app.get("/", response_model=Dict[str, str])
async def root():
    return {
        "message": "Web to Markdown Converter API",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        from crawl4ai import AsyncWebCrawler
        crawl4ai_available = True
    except ImportError:
        crawl4ai_available = False

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        crawl4ai_available=crawl4ai_available,
        timestamp=datetime.now().isoformat()
    )

@app.post("/convert", response_model=ConvertResponse)
async def convert_to_markdown(request: ConvertRequest):
    try:
        logger.info(f"Convert request received: {len(request.data) if isinstance(request.data, list) else 1} URL(s)")

        if request.use_antibot and request.antibot_mode not in ["stealth", "undetected", "combined"]:
            raise HTTPException(
                status_code=400,
                detail=f"Incorrect antibot mode: {request.antibot_mode}. Use: stealth, undetected, combined"
            )

        converter = WebToMarkdownConverter(
            delay=request.delay,
            timeout=request.timeout,
            use_antibot=request.use_antibot,
            antibot_mode=request.antibot_mode,
            headless=request.headless
        )

        if isinstance(request.data, list):
            url_list = [item.model_dump() for item in request.data]
        else:
            url_list = request.data.model_dump()

        results = await converter.get_cleaned_content_dict_async(url_list)

        if not results:
            return ConvertResponse(
                success=False,
                error="No articles could be processed.",
                processed_count=0
            )

        processed_count = len(results) if isinstance(results, list) else 1

        logger.info(f"{processed_count} pages successfully processed")

        return ConvertResponse(
            success=True,
            data=results,
            processed_count=processed_count
        )

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/convert/batch", response_model=ConvertResponse)
async def convert_batch(
    urls: List[HttpUrl],
    delay: float = 1.0,
    use_antibot: bool = False,
    antibot_mode: str = "stealth"
):
    url_data_list = [{"link": str(url)} for url in urls]

    request = ConvertRequest(
        data=[UrlData(**data) for data in url_data_list],
        delay=delay,
        use_antibot=use_antibot,
        antibot_mode=antibot_mode
    )

    return await convert_to_markdown(request)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": f"Internal server error: {str(exc)}",
            "timestamp": datetime.now().isoformat()
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
