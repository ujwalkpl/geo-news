FROM python:3.11-slim

WORKDIR /app

# Install shared dependencies
COPY shared/ /app/shared/
COPY services/poller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/poller/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
