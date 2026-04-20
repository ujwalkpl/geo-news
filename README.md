# GeoNews

A real-time geospatial news aggregator that plots news articles on an interactive globe.

## Prerequisites

- Docker + Docker Compose
- Node.js 18+
- Python 3.11+

## Running local infrastructure

Starts PostgreSQL, Redis, Kafka and Zookeeper:

```bash
cd infra
docker compose up -d
```

## Running the frontend

1. Copy `.env.example` to `.env` and fill in your Mapbox token (free at https://mapbox.com)

```bash
cp .env.example .env
```

2. Install dependencies and start the dev server

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Ports

| Service    | Port  |
|------------|-------|
| Frontend   | 5173  |
| Postgres   | 5433  |
| Redis      | 6379  |
| Kafka      | 9092  |
