FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV HF_DATASETS_CACHE=/app/.cache/huggingface/datasets

RUN mkdir -p /app/.cache/huggingface

RUN python -c "from transformers import pipeline; pipeline('zero-shot-classification', model='facebook/bart-large-mnli')"

COPY api.py .
# COPY classifier.py .

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8020/health')"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8020", "--workers", "1"]
