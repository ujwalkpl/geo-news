const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080'
const UPLOAD_BASE = import.meta.env.VITE_UPLOAD_URL || BASE

/**
 * Fetch a single article's full detail by ID.
 */
export async function fetchArticle(articleId, lang = 'en') {
  const res = await fetch(`${BASE}/news/${articleId}?lang=${lang}`)
  if (!res.ok) throw new Error(`Article fetch failed: ${res.status}`)
  return res.json()
}

/**
 * Post a like for an article (requires auth token for full functionality).
 */
export async function likeArticle(articleId, token = null) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/news/${articleId}/like`, {
    method: 'POST',
    headers,
  })
  if (!res.ok) throw new Error(`Like failed: ${res.status}`)
  return res.json()
}

/**
 * Fetch the paginated news feed.
 * @param {number} page
 * @param {string} category - 'All' or a specific category name
 * @returns {Promise<Array>}
 */
export async function fetchFeed(page = 1, category = 'All') {
  const cat = (!category || category === 'All') ? 'all' : category
  const params = new URLSearchParams({ category: cat, page: String(page) })
  const res = await fetch(`${BASE}/news/feed?${params}`)
  if (!res.ok) throw new Error(`Feed fetch failed: ${res.status}`)
  const data = await res.json()
  return data.articles ?? []
}

/**
 * Upload a user-reported article (two-step: signed URL → GCS PUT → confirm).
 * Requires a valid JWT token.
 */
export async function uploadArticle({ title, text, lat, lng, accuracy, image, token }) {
  let articleId = null
  let image_url = null

  if (image) {
    // Step 1: get a signed GCS upload URL
    const sigRes = await fetch(`${UPLOAD_BASE}/upload/signed-url`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        filename: image.name || 'photo.jpg',
        content_type: image.type || 'image/jpeg',
        size_bytes: image.size,
        lat,
        lng,
        accuracy,
      }),
    })
    if (!sigRes.ok) {
      const err = await sigRes.json().catch(() => ({}))
      throw Object.assign(new Error('Failed to get upload URL'), { response: { data: err } })
    }
    const { signed_url, image_url: gcsUrl, article_id: aid } = await sigRes.json()
    articleId = aid
    image_url = gcsUrl

    // Step 2: upload image directly to GCS (no auth header — signed URL is self-contained)
    const putRes = await fetch(signed_url, {
      method: 'PUT',
      headers: { 'Content-Type': image.type || 'image/jpeg' },
      body: image,
    })
    if (!putRes.ok) throw new Error('Image upload to storage failed')
  } else {
    // No image: generate a UUID client-side for the article
    articleId = crypto.randomUUID()
  }

  // Step 3: confirm and publish to pipeline
  const confirmRes = await fetch(`${UPLOAD_BASE}/upload/confirm`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      article_id: articleId,
      title: title || text.slice(0, 120),
      text,
      lat,
      lng,
      accuracy,
      image_url,
    }),
  })
  if (!confirmRes.ok) {
    const err = await confirmRes.json().catch(() => ({}))
    throw Object.assign(new Error('Upload confirmation failed'), { response: { data: err } })
  }
  return confirmRes.json()
}
