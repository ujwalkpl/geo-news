FROM python:3.11-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY services/summarizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model (not used here but image reused for other services)
COPY services/summarizer/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
