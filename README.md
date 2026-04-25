# GeoNews

Real-time geospatial news aggregator. Articles from NewsAPI and user reports are processed through an AI pipeline (summarization, classification, translation) and plotted as live dots on an interactive 3-D globe. Click any dot to read the story, filter by category, or report your own news with GPS.

## Architecture

Event-driven microservices on Google Cloud Run, connected via Kafka.

```
NewsAPI Poller ──┐
User Upload     ──┼──► raw-news (Kafka) ──► Summarizer ──► Classifier ──► Translator
                                                                                │
                                                                          Aggregator ──► Postgres
                                                                                │
                                                                         WebSocket ──► Browser
```

| Service | Role |
|---|---|
| `poller` | Polls NewsAPI every 5 min, publishes raw articles |
| `upload` | User GPS-tagged reports → GCS image upload → Kafka |
| `summarizer` | Gemini Flash — 2-sentence summary |
| `classifier` | spaCy NER + Google Maps Geocoding + keyword category |
| `translator` | MarianMT — translates to ES / FR / DE |
| `aggregator` | Joins all 3 AI results, writes to Postgres |
| `api` | FastAPI REST — map, feed, article detail, auth, likes |
| `websocket` | Pushes new articles to connected browsers in real time |
| `workers` | Score, heatmap, flush, and DLQ retry background jobs |

## Tech Stack

- **Frontend** — React + Vite, Mapbox GL JS, Framer Motion
- **Backend** — Python 3.11, FastAPI, asyncpg, confluent-kafka, redis-py
- **AI** — Gemini Flash (summaries), spaCy NER, HuggingFace MarianMT
- **Infra** — Postgres 15 + PostGIS, Redis 7, Confluent Kafka, Elasticsearch 8
- **Cloud** — Google Cloud Run, Cloud Storage, Cloud Scheduler, Secret Manager

## Local Development

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- React 19

### 1 — Start local infrastructure

```bash
cd infra
docker compose up -d
```

Starts Postgres + PostGIS, Redis, Kafka, Zookeeper, and Elasticsearch.

### 2 — Apply the database schema

```bash
psql postgresql://geonews:geonews@localhost:5433/geonews -f infra/schema.sql
```

### 3 — Frontend

```bash
cp frontend/.env.example frontend/.env   # add VITE_MAPBOX_TOKEN
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### 4 — Run a service locally (example: API)

```bash
cd services/api
pip install -r requirements.txt
PYTHONPATH=../../shared uvicorn main:app --reload --port 8080
```

### Local ports

| Service | Port |
|---|---|
| Frontend | 5173 |
| API | 8080 |
| Postgres | 5433 |
| Redis | 6379 |
| Kafka | 9092 |
| Elasticsearch | 9200 |

## Environment Variables

All secrets are stored in GCP Secret Manager for Cloud Run. For local dev, copy `.env.example` and fill in values.

| Variable | Description |
|---|---|
| `DATABASE_URL` | asyncpg Postgres connection string |
| `REDIS_URL` | Redis connection string |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address |
| `JWT_SECRET` | Secret for signing JWTs |
| `GCS_BUCKET` | GCS bucket name for image uploads |
| `NEWSAPI_KEY` | [newsapi.org](https://newsapi.org) API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GOOGLE_MAPS_API_KEY` | Google Maps Geocoding API key |
| `MAPBOX_TOKEN` | Mapbox public token (frontend) |
| `VITE_API_URL` | API service public URL (baked into frontend build) |
| `VITE_WS_URL` | WebSocket service URL (baked into frontend build) |
| `VITE_UPLOAD_URL` | Upload service URL (baked into frontend build) |

## Deployment

CI/CD runs via GitHub Actions (`.github/workflows/deploy.yml`). On every push to `main`, only services with changed files are rebuilt and redeployed to Cloud Run.

To force a full redeploy of all services, include `[deploy all]` in the commit message.

### GitHub Secrets required

| Secret | How to obtain |
|---|---|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCP_SA_KEY` | Service account key JSON encoded as base64: `cat key.json \| base64` |
| `GCP_REGION` | Cloud Run region e.g. `us-central1` |
| `AR_REPO` | Artifact Registry repository name |
| *(all env vars above)* | Add each as a GitHub secret with the same name |
