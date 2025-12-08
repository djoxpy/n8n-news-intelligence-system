from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn
from transformers import pipeline
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="News Article Classifier API",
    description="Zero-shot classification API for news articles",
    version="1.0.0"
)

classifier = None
CONFIDENCE_THRESHOLD = 0.60

class Article(BaseModel):
    title: str = Field(..., description="Article title")
    contentSnippet: str = Field(..., description="Summary of the article")

    class Config:
        extra = "allow"

class ClassifiedArticle(BaseModel):
    title: str
    contentSnippet: str
    category: str
    confidence: float
    threshold_applied: bool

    class Config:
        extra = "allow"

class ClassifyRequest(BaseModel):
    articles: List[Article] = Field(..., description="Array of articles for classification")
    threshold: Optional[float] = Field(
        CONFIDENCE_THRESHOLD,
        ge=0.0,
        le=1.0,
        description="Confidence threshold (0.0-1.0)"
    )

class ClassifyResponse(BaseModel):
    articles: List[ClassifiedArticle]
    total: int
    statistics: dict

@app.on_event("startup")
async def load_model():
    global classifier
    logger.info("Loading zero-shot classification model...")
    try:
        classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1
        )
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

def classify_article(article: dict, threshold: float = CONFIDENCE_THRESHOLD) -> dict:
    content_snippet = article.get('contentSnippet', '')[:250]
    text = f"{article['title']}. {content_snippet}"

    relevant_categories = ["relevant_politics", "relevant_tech"]
    result = classifier(text, relevant_categories)

    best_category = result['labels'][0]
    best_confidence = result['scores'][0]

    if best_confidence < threshold:
        final_category = "not_relevant"
        final_confidence = 1.0 - best_confidence
        threshold_applied = True
    else:
        final_category = best_category
        final_confidence = best_confidence
        threshold_applied = False

    classified = {
        **article,
        'category': final_category,
        'confidence': final_confidence,
        'threshold_applied': threshold_applied
    }

    return classified

@app.post("/classify", response_model=ClassifyResponse)
async def classify_articles(request: ClassifyRequest):
    if not classifier:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        classified_articles = []
        for article in request.articles:
            article_dict = article.dict()
            classified = classify_article(article_dict, request.threshold)
            classified_articles.append(classified)

        stats = {}
        for article in classified_articles:
            cat = article['category']
            stats[cat] = stats.get(cat, 0) + 1

        return ClassifyResponse(
            articles=classified_articles,
            total=len(classified_articles),
            statistics=stats
        )

    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": classifier is not None
    }

@app.get("/")
async def root():
    return {
        "name": "News Article Classifier API",
        "version": "1.0.0",
        "endpoints": {
            "POST /classify": "Classify articles",
            "GET /health": "Health check",
            "GET /docs": "Swagger documentation"
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8020)
