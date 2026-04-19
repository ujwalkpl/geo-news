FROM python:3.11-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY services/workers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/workers/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1

# WORKER_NAME is set per Cloud Run job: score_worker | flush_worker | heatmap_worker | dlq_retry_worker
# For scheduler-triggered workers, each is its own Cloud Run service with its own CMD
EXPOSE 8080
CMD ["uvicorn", "score_worker:app", "--host", "0.0.0.0", "--port", "8080"]
