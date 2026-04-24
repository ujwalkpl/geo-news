FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/translator/requirements.txt .
# Install CPU-only PyTorch first (avoids pulling the large CUDA build)
RUN pip install --no-cache-dir \
    torch==2.3.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download MarianMT models during build so there's no cold-start latency
RUN python -c "\
from transformers import MarianMTModel, MarianTokenizer; \
pairs = ['Helsinki-NLP/opus-mt-en-es','Helsinki-NLP/opus-mt-en-fr','Helsinki-NLP/opus-mt-en-de']; \
[MarianMTModel.from_pretrained(p) and MarianTokenizer.from_pretrained(p) for p in pairs]"

COPY services/translator/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1
# min-instances: 1 in Cloud Run (avoid cold start for model loading)

CMD ["python", "main.py"]
