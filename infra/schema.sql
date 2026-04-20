-- GeoNews Database Schema
-- PostgreSQL 15 + PostGIS

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for text search acceleration

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    username      TEXT UNIQUE NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_seen     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ============================================================
-- ARTICLES
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
    article_id     UUID PRIMARY KEY,                        -- generated at ingestion
    source         VARCHAR(20) NOT NULL,                    -- 'newsapi' or 'user_upload'
    original_url   TEXT,
    title          TEXT NOT NULL,
    body           TEXT,
    image_url      TEXT,
    author         TEXT,
    published_at   TIMESTAMPTZ NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    status         VARCHAR(20) DEFAULT 'pending',           -- pending | processed | failed
    category       VARCHAR(50),
    geo_place_name TEXT,
    location       GEOGRAPHY(POINT, 4326),                  -- PostGIS point (lng, lat)
    language       VARCHAR(10)
);

-- Geospatial index — critical for ST_Within bbox queries
CREATE INDEX IF NOT EXISTS idx_articles_location           ON articles USING GIST(location);
-- Covering index for feed queries
CREATE INDEX IF NOT EXISTS idx_articles_category_published ON articles(category, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_published          ON articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_status             ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_source             ON articles(source);

-- ============================================================
-- ARTICLE TRANSLATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS article_translations (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id    UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    language_code VARCHAR(10) NOT NULL,
    title         TEXT,
    summary       TEXT,
    UNIQUE(article_id, language_code)
);

CREATE INDEX IF NOT EXISTS idx_translations_article ON article_translations(article_id);

-- ============================================================
-- ARTICLE ENGAGEMENT
-- ============================================================
CREATE TABLE IF NOT EXISTS article_engagement (
    article_id  UUID PRIMARY KEY REFERENCES articles(article_id) ON DELETE CASCADE,
    likes       INT DEFAULT 0,
    dislikes    INT DEFAULT 0,
    view_count  INT DEFAULT 0,
    score       FLOAT DEFAULT 0,           -- precomputed time-decay score
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engagement_score ON article_engagement(score DESC);
-- Partial index — only indexes articles with score > 0 (hot articles)
CREATE INDEX IF NOT EXISTS idx_engagement_score_positive ON article_engagement(score DESC)
    WHERE score > 0;

-- ============================================================
-- USER REACTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS user_reactions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    article_id  UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    reaction    VARCHAR(10) NOT NULL CHECK (reaction IN ('like', 'dislike')),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, article_id)           -- one reaction per user per article
);

CREATE INDEX IF NOT EXISTS idx_user_reactions_user    ON user_reactions(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_reactions_article ON user_reactions(article_id);

-- ============================================================
-- HEATMAP MATERIALIZED VIEW
-- Refreshed every 5 minutes by heatmap_worker
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS heatmap_points AS
SELECT
    article_id,
    location,
    category,
    score
FROM articles a
LEFT JOIN article_engagement ae USING (article_id)
WHERE
    a.published_at > NOW() - INTERVAL '24 hours'
    AND a.status = 'processed'
    AND a.location IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_heatmap_location ON heatmap_points USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_heatmap_category ON heatmap_points(category);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Auto-create engagement row when an article is inserted
CREATE OR REPLACE FUNCTION create_engagement_row()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO article_engagement (article_id)
    VALUES (NEW.article_id)
    ON CONFLICT (article_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_create_engagement
AFTER INSERT ON articles
FOR EACH ROW EXECUTE FUNCTION create_engagement_row();

-- Time-decay score formula: (likes - dislikes) / (age_hours + 2)^1.8
CREATE OR REPLACE FUNCTION compute_score(
    p_likes        INT,
    p_dislikes     INT,
    p_published_at TIMESTAMPTZ
) RETURNS FLOAT AS $$
DECLARE
    age_hours FLOAT;
BEGIN
    age_hours := EXTRACT(EPOCH FROM (NOW() - p_published_at)) / 3600.0;
    RETURN (p_likes - p_dislikes)::FLOAT / POWER(age_hours + 2.0, 1.8);
END;
$$ LANGUAGE plpgsql IMMUTABLE;
