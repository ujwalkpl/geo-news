FROM python:3.11-slim

WORKDIR /app

# Install system deps for spaCy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY shared/ /app/shared/
COPY services/classifier/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

COPY services/classifier/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
