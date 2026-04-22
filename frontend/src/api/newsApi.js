const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080'

/**
 * Fetch articles within a map bounding box.
 * @param {Object} params
 * @param {string} params.bbox   - "swLat,swLng,neLat,neLng"
 * @param {string} params.category - category filter or "all"
 * @returns {Promise<Array>}     - array of article stubs
 */
export async function fetchMapArticles({ bbox, category = 'all' }) {
  const params = new URLSearchParams({ bbox, category })
  const res = await fetch(`${BASE}/news/map?${params}`)
  if (!res.ok) throw new Error(`Map fetch failed: ${res.status}`)
  const data = await res.json()
  return data.articles ?? []
}

/**
 * Fetch a single article by ID.
 * @param {string} articleId
 * @param {string} lang
 */
export async function fetchArticle(articleId, lang = 'en') {
  const res = await fetch(`${BASE}/news/${articleId}?lang=${lang}`)
  if (!res.ok) throw new Error(`Article fetch failed: ${res.status}`)
  return res.json()
}

/**
 * Post a like or dislike reaction (requires auth token).
 * @param {string} articleId
 * @param {'like'|'dislike'} reaction
 * @param {string} token  - JWT access token
 */
export async function reactToArticle(articleId, reaction, token) {
  const res = await fetch(`${BASE}/news/${articleId}/${reaction}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error(`Reaction failed: ${res.status}`)
  return res.json()
}
