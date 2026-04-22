FROM python:3.11-slim

WORKDIR /app

COPY shared/ /app/shared/
COPY services/aggregator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/aggregator/ /app/

ENV PYTHONPATH=/app/shared
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
