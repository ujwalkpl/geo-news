FROM python:3.11-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY services/websocket/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/websocket/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Single worker — WebSocket state is in-process (session affinity on Cloud Run)
# min-instances: 1 in Cloud Run to avoid cold start dropping WS connections
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
